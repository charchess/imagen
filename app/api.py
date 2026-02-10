import hmac
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from celery.result import AsyncResult
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from app.config import *
from app.config import LORAS_CIVITAI_DIR, CATEGORY_SUBTYPES, REFERENCE_CATEGORIES
from app.worker import celery_app, generate_image_task
from app.models_config import (
    AVAILABLE_MODELS,
    get_all_loras,
    get_model_config,
    get_lora_config,
    DEFAULT_MODEL
)
from app.model_manager import ModelManager
from app.references import ReferenceManager, ReferenceRequest

app = FastAPI(title="Imagen API - SDXL Generation", version="2.0")
v1_router = APIRouter(prefix="/v1")

# Servir les images générées et les references
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/reference", StaticFiles(directory=REFERENCE_DIR), name="reference")

# Fichier de tracking des images recuperees
RETRIEVAL_TRACKER = OUTPUTS_DIR / ".retrieved.json"


def _load_retrieved() -> Dict[str, str]:
    """Charge le tracker des images recuperees {filename: retrieved_at}"""
    if not RETRIEVAL_TRACKER.exists():
        return {}
    try:
        return json.loads(RETRIEVAL_TRACKER.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return {}


def _mark_retrieved(filename: str) -> None:
    """Marque une image comme recuperee"""
    tracker = _load_retrieved()
    tracker[filename] = datetime.now(timezone.utc).isoformat()
    RETRIEVAL_TRACKER.write_text(
        json.dumps(tracker, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ============================================
# ERROR HANDLING
# ============================================


class ImagenAPIError(Exception):
    """Standardized API error with error envelope response."""
    def __init__(self, code: str, message: str, detail: str = "", status: int = 500):
        self.code = code
        self.message = message
        self.detail = detail
        self.status = status


@app.exception_handler(ImagenAPIError)
async def imagen_error_handler(request: Request, exc: ImagenAPIError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail, "status": exc.status}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_PARAMETERS", "message": "Validation failed", "detail": exc.errors(), "status": 422}},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "detail": "", "status": 500}},
    )


# ============================================
# API KEY AUTHENTICATION
# ============================================

API_KEY_FILE = Path("/app/secrets/api_key.txt")

EXEMPT_ROUTES = [
    ("GET", "/health"),
    ("GET", "/v1/models"),
    ("GET", "/v1/loras"),
    ("GET", "/v1/references"),
]


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Exempt specific routes (read-only discovery + infrastructure)
        for method, path in EXEMPT_ROUTES:
            if request.method == method and request.url.path == path:
                return await call_next(request)

        # Exempt StaticFiles mounts
        if request.url.path.startswith("/outputs/") or request.url.path.startswith("/reference/"):
            return await call_next(request)

        # Exempt OpenAPI/docs endpoints
        if request.url.path in ("/openapi.json", "/docs", "/redoc"):
            return await call_next(request)

        # Read key from file on every request (hot rotation support, no caching)
        if not API_KEY_FILE.exists():
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "API key not configured", "detail": "", "status": 401}},
            )

        expected_key = API_KEY_FILE.read_text(encoding="utf-8").strip()
        provided_key = request.headers.get("X-API-Key", "")

        if not provided_key or not hmac.compare_digest(provided_key, expected_key):
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "Invalid or missing API key", "detail": "", "status": 401}},
            )

        return await call_next(request)


app.add_middleware(APIKeyMiddleware)


# ============================================
# SCHEMAS
# ============================================

class LoRARequest(BaseModel):
    """Configuration d'un LoRA pour la génération"""
    name: str = Field(description="ID du LoRA (de AVAILABLE_LORAS)")
    weight: float = Field(default=0.8, ge=0.0, le=2.0, description="Poids du LoRA")


class GenerationReferenceRequest(BaseModel):
    """Reference a utiliser pour la generation"""
    entity: str = Field(description="Nom de l'entite (ex: electra, cuisine)")
    types: List[str] = Field(
        default=["front"],
        description="Sous-types a utiliser (ex: front, side)"
    )
    strength: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Force du style transfer (0.4-0.6 recommande pour personnages)"
    )


class GenerationRequest(BaseModel):
    """Requête de génération d'image"""
    # Paramètres de base
    prompt: str = Field(description="Description de l'image à générer")
    negative_prompt: Optional[str] = Field(
        default=None,
        description="Éléments à éviter (auto-rempli selon le modèle si None)"
    )

    # Style transfer (legacy)
    ip_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="(Legacy) Force du style transfer via IP-Adapter (0.0 = désactivé). Utiliser 'references' de preference."
    )

    # References graphiques
    references: List[GenerationReferenceRequest] = Field(
        default=[],
        description="References graphiques a utiliser (personnage, background, pose)"
    )

    # Multi-modèles & LoRA
    model: str = Field(
        default=DEFAULT_MODEL,
        description="ID du modèle base à utiliser"
    )
    loras: List[LoRARequest] = Field(
        default=[],
        description="Liste des LoRAs à appliquer"
    )

    # Paramètres de génération
    steps: int = Field(
        default=30,
        ge=10,
        le=100,
        description="Nombre d'étapes de diffusion"
    )
    guidance_scale: float = Field(
        default=7.5,
        ge=1.0,
        le=30.0,
        description="Classifier-Free Guidance scale"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Seed pour reproductibilité (None = aléatoire)"
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-set negative prompt selon le modèle si non fourni
        if self.negative_prompt is None:
            model_config = get_model_config(self.model)
            if model_config:
                self.negative_prompt = model_config.default_negative
            else:
                self.negative_prompt = "low quality, blurry, distorted"


class GenerationResponse(BaseModel):
    """Réponse de création de tâche"""
    job_id: str
    status: str
    message: str


@v1_router.post("/generate", response_model=GenerationResponse)
async def create_generation_task(request: GenerationRequest):
    """
    Crée une tâche de génération d'image.

    Supporte:
    - Multi-modèles (SDXL, PonyXL, etc.)
    - LoRAs multiples
    - Paramètres configurables (steps, guidance_scale, seed)
    - Style transfer (IP-Adapter)

    Retourne immédiatement un job_id pour polling.
    """
    try:
        # Valider le modèle demandé
        if request.model not in AVAILABLE_MODELS:
            raise ImagenAPIError(
                code="MODEL_NOT_FOUND",
                message=f"Model '{request.model}' not available",
                detail=f"Available models: {list(AVAILABLE_MODELS.keys())}",
                status=404,
            )

        # Valider les LoRAs demandés
        all_loras = get_all_loras()
        for lora_req in request.loras:
            if lora_req.name not in all_loras:
                raise ImagenAPIError(
                    code="LORA_NOT_FOUND",
                    message=f"LoRA '{lora_req.name}' not available",
                    detail=f"Available LoRAs: {list(all_loras.keys())}",
                    status=404,
                )

        # Valider les references et resoudre les chemins
        resolved_refs = []
        prompt = request.prompt
        negative_prompt = request.negative_prompt or ""

        if request.references and request.ip_strength > 0:
            raise ImagenAPIError(
                code="INVALID_PARAMETERS",
                message="Cannot use both 'references' and 'ip_strength'",
                detail="Use 'references' instead of 'ip_strength'.",
                status=422,
            )

        if request.references:
            try:
                resolved_refs = ReferenceManager.resolve_references(
                    [ReferenceRequest(entity=r.entity, types=r.types, strength=r.strength)
                     for r in request.references]
                )
            except ValueError as e:
                raise ImagenAPIError(
                    code="REFERENCE_NOT_FOUND",
                    message="Reference resolution failed",
                    detail=str(e),
                    status=404,
                )

            # Auto-injection fond blanc pour references de type character
            has_character_ref = any(r.get("category") == "character" for r in resolved_refs)
            if has_character_ref:
                if "white background" not in prompt.lower():
                    prompt = f"{prompt}, white background, simple background"
                if "complex background" not in negative_prompt.lower():
                    negative_prompt = f"{negative_prompt}, complex background, detailed background"

        # Vérifier queue (protection contre burst CLI)
        inspector = celery_app.control.inspect()
        active = inspector.active() or {}
        scheduled = inspector.scheduled() or {}

        total_pending = sum(len(t) for t in {**active, **scheduled}.values())

        if total_pending >= MAX_QUEUE_SIZE:
            raise ImagenAPIError(
                code="QUEUE_FULL",
                message="Generation queue is saturated",
                detail=f"Current queue size: {total_pending}/{MAX_QUEUE_SIZE}. Retry after a few minutes.",
                status=503,
            )

        # Soumission tâche avec TOUS les paramètres
        task = generate_image_task.delay(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=request.model,
            loras=[lora.dict() for lora in request.loras],
            steps=request.steps,
            guidance_scale=request.guidance_scale,
            seed=request.seed,
            ip_strength=request.ip_strength,
            references=[
                {"path": r["path"], "strength": r["strength"], "embedding_path": r.get("embedding_path")}
                for r in resolved_refs
            ],
        )

        return GenerationResponse(
            job_id=task.id,
            status="queued",
            message=f"Tâche en file d'attente. Position estimée: {total_pending + 1}",
        )

    except ImagenAPIError:
        raise
    except Exception as e:
        raise ImagenAPIError(
            code="INTERNAL_ERROR",
            message="Internal server error",
            detail=str(e),
            status=500,
        )


@v1_router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Récupère le statut d'une génération
    """
    task_result = AsyncResult(job_id, app=celery_app)

    # Job doesn't exist (PENDING with no result means never submitted)
    if task_result.state == "PENDING" and not task_result.result:
        raise ImagenAPIError(
            code="JOB_NOT_FOUND",
            message="Job not found",
            detail=f"No job with ID '{job_id}' exists.",
            status=404,
        )

    response = {"job_id": job_id, "status": task_result.status, "result": None}

    if task_result.status == "SUCCESS":
        response["result"] = task_result.result
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.result)
    elif task_result.status == "PROGRESS":
        response["meta"] = task_result.info

    return response


@v1_router.get("/download/{filename}")
async def download_image(filename: str):
    """
    Télécharge une image générée par son nom de fichier.
    Marque l'image comme recuperee pour le nettoyage ulterieur.
    """
    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        raise ImagenAPIError(
            code="IMAGE_NOT_FOUND",
            message="Image not found",
            detail=f"File '{filename}' does not exist.",
            status=404,
        )

    _mark_retrieved(filename)

    return FileResponse(file_path, media_type="image/png", filename=filename)


@v1_router.get("/image/{job_id}")
async def get_image_by_job_id(job_id: str):
    """
    Récupère directement l'image PNG par job_id.

    Exemple: GET /image/7f2b0887-3cdf-46ff-b83b-ff7685ac5b23
    Retourne: L'image PNG si la génération est terminée

    Status codes:
    - 200: Image retournée
    - 202: Génération en cours (Accepted)
    - 404: Job non trouvé
    - 500: Erreur lors de la génération
    """
    task_result = AsyncResult(job_id, app=celery_app)

    # Job n'existe pas
    if task_result.state == "PENDING" and not task_result.result:
        raise ImagenAPIError(
            code="JOB_NOT_FOUND",
            message="Job not found",
            detail=f"No job with ID '{job_id}' exists.",
            status=404,
        )

    # Génération en cours
    if task_result.state in ["PENDING", "PROGRESS", "STARTED"]:
        raise HTTPException(
            status_code=202,
            detail={
                "status": "processing",
                "message": "Image en cours de génération",
                "state": task_result.state,
                "meta": task_result.info if task_result.state == "PROGRESS" else None
            }
        )

    # Échec de génération
    if task_result.state == "FAILURE":
        raise ImagenAPIError(
            code="GENERATION_FAILED",
            message="Image generation failed",
            detail=str(task_result.result),
            status=500,
        )

    # Succès - récupérer le fichier
    if task_result.state == "SUCCESS":
        result = task_result.result
        filename = result.get("filename")

        if not filename:
            raise ImagenAPIError(
                code="INTERNAL_ERROR",
                message="Internal server error",
                detail="Filename not found in result.",
                status=500,
            )

        file_path = OUTPUTS_DIR / filename

        if not file_path.exists():
            raise ImagenAPIError(
                code="IMAGE_NOT_FOUND",
                message="Image not found",
                detail=f"Generated file '{filename}' not found on disk.",
                status=404,
            )

        # Marquer comme recuperee
        _mark_retrieved(filename)

        return FileResponse(
            file_path,
            media_type="image/png",
            filename=filename,
            headers={
                "X-Job-ID": job_id,
                "X-Generation-Metadata": str(result.get("metadata", {}))
            }
        )

    # État inconnu
    raise ImagenAPIError(
        code="INTERNAL_ERROR",
        message="Internal server error",
        detail=f"Unknown task state: {task_result.state}",
        status=500,
    )


@v1_router.get("/models")
async def list_models():
    """
    Liste les modèles disponibles avec leur état d'installation.

    Returns:
        Liste des modèles avec nom court, nom complet et statut
    """
    models = []
    for model_id, config in AVAILABLE_MODELS.items():
        is_installed = ModelManager.is_model_installed(
            config.path,
            config.checkpoint_url
        )

        models.append({
            "id": model_id,
            "short_name": config.short_name,
            "full_name": config.full_name,
            "description": config.description,
            "supported_loras": config.supported_loras,
            "default_negative": config.default_negative,
            "installed": is_installed,
            "path": config.path
        })

    # Infos sur les modèles installés
    installed_models = ModelManager.get_installed_models()

    return {
        "models": models,
        "default_model": DEFAULT_MODEL,
        "installed_count": sum(1 for m in models if m["installed"]),
        "cache_info": installed_models
    }


@v1_router.get("/loras")
async def list_loras():
    """
    Liste les LoRAs disponibles avec leur référence et état d'installation.

    Returns:
        Liste des LoRAs avec référence (civitai-XXX, huggingface-XXX) et description
    """
    all_loras = get_all_loras()
    loras = []

    for lora_id, config in all_loras.items():
        is_installed = ModelManager.is_lora_installed(config.path)

        loras.append({
            "id": lora_id,
            "name": config.name,
            "reference": config.reference,
            "source": config.source,
            "description": config.description,
            "default_weight": config.default_weight,
            "trigger_words": config.trigger_words,
            "installed": is_installed,
            "path": config.path
        })

    # Infos sur les LoRAs installés
    installed_loras = ModelManager.get_installed_loras()

    return {
        "loras": loras,
        "total": len(loras),
        "installed_count": sum(1 for l in loras if l["installed"]),
        "installed_details": installed_loras
    }


# ============================================
# REFERENCES CRUD
# ============================================


class CreateEntityRequest(BaseModel):
    """Requete de creation d'entite de reference"""
    category: str = Field(description="Categorie: character, background, pose")
    description: Optional[str] = Field(default=None, description="Description de l'entite")


@v1_router.post("/references/{entity_name}", status_code=201)
async def create_reference_entity(entity_name: str, request: CreateEntityRequest):
    """Cree une nouvelle entite de reference (personnage, background, pose)."""
    try:
        entity = ReferenceManager.create_entity(
            name=entity_name,
            category=request.category,
            description=request.description,
        )
        return {
            "entity": entity_name,
            "category": entity.category,
            "description": entity.description,
            "created_at": entity.created_at,
            "references": {},
            "status": "created",
        }
    except ValueError as e:
        msg = str(e)
        if "existe deja" in msg:
            raise ImagenAPIError(
                code="INVALID_PARAMETERS",
                message="Entity already exists",
                detail=msg,
                status=409,
            )
        raise ImagenAPIError(
            code="INVALID_PARAMETERS",
            message="Invalid entity parameters",
            detail=msg,
            status=422,
        )


@v1_router.post("/references/{entity_name}/{subtype}", status_code=201)
async def upload_reference_image(
    entity_name: str,
    subtype: str,
    file: UploadFile = File(...),
):
    """Upload une image de reference pour une entite existante."""
    try:
        image_data = await file.read()
        ref_image = ReferenceManager.upload_image(
            entity_name=entity_name,
            subtype=subtype,
            image_data=image_data,
            original_filename=file.filename or "unknown.png",
        )

        # Lancer le calcul d'embedding en arriere-plan
        from app.worker import compute_embedding_task
        embedding_task = compute_embedding_task.delay(entity_name, subtype)

        return {
            "entity": entity_name,
            "subtype": subtype,
            "filename": ref_image.filename,
            "original_name": ref_image.original_name,
            "dimensions": {"width": ref_image.width, "height": ref_image.height},
            "embedding_status": "computing",
            "embedding_job_id": embedding_task.id,
        }
    except ValueError as e:
        msg = str(e)
        if "non trouvee" in msg:
            raise ImagenAPIError(
                code="REFERENCE_NOT_FOUND",
                message="Reference entity not found",
                detail=msg,
                status=404,
            )
        if "trop volumineux" in msg:
            raise ImagenAPIError(
                code="INVALID_PARAMETERS",
                message="File too large",
                detail=msg,
                status=413,
            )
        if "non supporte" in msg or "Impossible de lire" in msg:
            raise ImagenAPIError(
                code="INVALID_PARAMETERS",
                message="Unsupported file format",
                detail=msg,
                status=415,
            )
        raise ImagenAPIError(
            code="INVALID_PARAMETERS",
            message="Invalid reference parameters",
            detail=msg,
            status=422,
        )


@v1_router.get("/references")
async def list_references(category: Optional[str] = Query(default=None)):
    """Liste toutes les entites de reference, avec filtre optionnel par categorie."""
    if category and category not in REFERENCE_CATEGORIES:
        raise ImagenAPIError(
            code="INVALID_PARAMETERS",
            message="Invalid category",
            detail=f"Valid categories: {', '.join(REFERENCE_CATEGORIES)}",
            status=422,
        )

    entities = ReferenceManager.list_entities(category=category)

    result = {}
    category_counts: Dict[str, int] = {c: 0 for c in REFERENCE_CATEGORIES}

    for name, entity in entities.items():
        category_counts[entity.category] = category_counts.get(entity.category, 0) + 1
        result[name] = {
            "category": entity.category,
            "description": entity.description,
            "reference_count": len(entity.references),
            "subtypes": list(entity.references.keys()),
            "all_embeddings_cached": all(
                r.embedding_cached for r in entity.references.values()
            ) if entity.references else False,
        }

    return {
        "entities": result,
        "total": len(result),
        "categories": category_counts,
    }


@v1_router.get("/references/{entity_name}")
async def get_reference_entity(entity_name: str):
    """Details d'une entite de reference avec toutes ses images."""
    entity = ReferenceManager.get_entity(entity_name)
    if not entity:
        raise ImagenAPIError(
            code="REFERENCE_NOT_FOUND",
            message="Reference entity not found",
            detail=f"Entity '{entity_name}' does not exist.",
            status=404,
        )

    from app.references import CATEGORY_DIRS
    subdir = CATEGORY_DIRS.get(entity.category, entity.category)

    references = {}
    for subtype, ref_img in entity.references.items():
        references[subtype] = {
            "filename": ref_img.filename,
            "original_name": ref_img.original_name,
            "dimensions": {"width": ref_img.width, "height": ref_img.height},
            "uploaded_at": ref_img.uploaded_at,
            "embedding_cached": ref_img.embedding_cached,
            "url": f"/reference/{subdir}/{entity_name}/{ref_img.filename}",
        }

    return {
        "entity": entity_name,
        "category": entity.category,
        "description": entity.description,
        "created_at": entity.created_at,
        "references": references,
    }


@v1_router.delete("/references/{entity_name}")
async def delete_reference_entity(entity_name: str):
    """Supprime une entite et toutes ses images."""
    try:
        images_count = ReferenceManager.delete_entity(entity_name)
        return {
            "status": "deleted",
            "entity": entity_name,
            "images_removed": images_count,
        }
    except ValueError as e:
        raise ImagenAPIError(
            code="REFERENCE_NOT_FOUND",
            message="Reference entity not found",
            detail=str(e),
            status=404,
        )


@v1_router.delete("/references/{entity_name}/{subtype}")
async def delete_reference_image(entity_name: str, subtype: str):
    """Supprime une image de reference specifique."""
    try:
        ReferenceManager.delete_image(entity_name, subtype)
        return {
            "status": "deleted",
            "entity": entity_name,
            "subtype": subtype,
        }
    except ValueError as e:
        raise ImagenAPIError(
            code="REFERENCE_NOT_FOUND",
            message="Reference image not found",
            detail=str(e),
            status=404,
        )


# ============================================
# CIVITAI DOWNLOAD
# ============================================


class CivitaiDownloadRequest(BaseModel):
    """Requête de téléchargement depuis Civitai"""
    model_id: int = Field(description="ID du modèle sur Civitai")
    lora_id: str = Field(description="ID local pour le LoRA (ex: civitai-123456)")
    filename: Optional[str] = Field(default=None, description="Nom du fichier (optionnel)")


@v1_router.post("/download/civitai")
async def download_from_civitai(request: CivitaiDownloadRequest):
    """
    Télécharge un LoRA depuis Civitai et l'ajoute aux LoRAs disponibles.

    Args:
        model_id: ID du modèle sur Civitai
        lora_id: ID local pour référencer le LoRA (ex: civitai-123456)
        filename: Nom du fichier de sortie (optionnel)

    Returns:
        Statut du téléchargement
    """
    try:
        # Créer le dossier de destination dans loras/civitai/
        output_dir = LORAS_CIVITAI_DIR / f"civitai_{request.model_id}"

        # Télécharger
        downloaded_path = ModelManager.download_from_civitai(
            model_id=request.model_id,
            output_dir=output_dir,
            filename=request.filename
        )

        if not downloaded_path:
            raise ImagenAPIError(
                code="DOWNLOAD_FAILED",
                message="Download failed",
                detail="CivitAI download returned no file.",
                status=500,
            )

        return {
            "status": "success",
            "message": f"LoRA téléchargé avec succès",
            "lora_id": request.lora_id,
            "reference": f"civitai-{request.model_id}",
            "path": str(downloaded_path.relative_to(MODELS_DIR.parent)),
            "size_mb": round(downloaded_path.stat().st_size / (1024**2), 1)
        }

    except ImagenAPIError:
        raise
    except Exception as e:
        raise ImagenAPIError(
            code="INTERNAL_ERROR",
            message="Internal server error",
            detail=str(e),
            status=500,
        )


@app.get("/health")
async def health_check():
    """Healthcheck pour monitoring"""
    return {
        "status": "ok",
        "gpu_available": True,  # Simplifié pour l'exemple
        "queue_broker": "connected",
    }


app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
