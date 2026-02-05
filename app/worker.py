import os
import sys
import multiprocessing
multiprocessing.set_start_method('spawn', force=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gc
import uuid
from datetime import datetime

import torch
from celery import Celery

from app.config import *
from app.pipeline import pipeline
from app.references import ReferenceManager

# Configuration Celery
celery_app = Celery(
    "electra_worker", broker=REDIS_URL, backend=REDIS_URL, include=["app.worker"]
)

# IMPORTANT : Concurrency = 1 pour GPU (11Go VRAM)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 min max par image
    worker_concurrency=1,  # CRITICAL : Un seul job GPU à la fois
    worker_prefetch_multiplier=1,
    result_expires=3600,  # Résultats stockés 1h
)


@celery_app.task(bind=True, max_retries=3)
def generate_image_task(
    self,
    prompt: str,
    negative_prompt: str = "",
    model: str = "sdxl",
    loras: list = [],
    steps: int = 30,
    guidance_scale: float = 7.5,
    seed: int = None,
    ip_strength: float = 0.0,
    references: list = [],
):
    """
    Task Celery pour génération sur GPU avec support multi-modèles, LoRA et references

    Args:
        prompt: Description de l'image
        negative_prompt: Éléments à éviter
        model: ID du modèle base
        loras: Liste des LoRAs [{name, weight}, ...]
        steps: Nombre d'étapes de diffusion
        guidance_scale: CFG scale
        seed: Seed pour reproductibilité
        ip_strength: (Legacy) Force du style transfer (0.0-1.0)
        references: Liste de references [{path, strength, embedding_path}, ...]

    Returns:
        Dict avec status, filename, path, url et metadata
    """
    try:
        self.update_state(state="PROGRESS", meta={"step": "initialisation"})

        # Génération ID unique
        job_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Nom de fichier avec préfixe du modèle
        model_prefix = model.replace("-", "_")
        filename = f"{model_prefix}_{timestamp}_{job_id}.png"
        output_path = OUTPUTS_DIR / filename

        # Résolution des references
        reference_images = None
        ref_path = None

        if references:
            # Nouveau systeme de references
            reference_images = references
        elif ip_strength > 0:
            # Legacy: image de reference hardcodee
            legacy_ref = REFERENCE_DIR / "electra_ref.png"
            if legacy_ref.exists():
                ref_path = str(legacy_ref)

        self.update_state(
            state="PROGRESS", meta={"step": "generation_gpu", "progress": 10}
        )

        # Génération avec TOUS les paramètres
        image = pipeline.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            loras=loras,
            steps=steps,
            guidance_scale=guidance_scale,
            seed=seed,
            reference_image_path=ref_path,
            ip_strength=ip_strength,
            reference_images=reference_images,
        )

        self.update_state(state="PROGRESS", meta={"step": "sauvegarde", "progress": 90})

        # Sauvegarde
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, "PNG")

        self.update_state(state="PROGRESS", meta={"step": "termine", "progress": 100})

        # Retour avec metadata complète
        return {
            "status": "success",
            "filename": filename,
            "path": str(output_path.relative_to(BASE_DIR)),
            "url": f"/outputs/{filename}",
            "metadata": {
                "model": model,
                "loras": loras,
                "steps": steps,
                "guidance_scale": guidance_scale,
                "seed": seed,
                "ip_strength": ip_strength,
                "references": [
                    {"path": r["path"], "strength": r["strength"]}
                    for r in (references or [])
                ],
            }
        }

    except Exception as exc:
        print(f"❌ Erreur task: {exc}")
        # Retry après 10s en cas d'OOM éventuel
        self.retry(countdown=10, exc=exc)


@celery_app.task(bind=True, max_retries=1)
def compute_embedding_task(self, entity_name: str, subtype: str):
    """
    Valide et marque une reference comme prete.
    Le pre-calcul d'embeddings sera ajoute avec IP-Adapter Plus (Phase 2).
    Pour l'instant, les images brutes sont utilisees directement.
    """
    try:
        image_path = ReferenceManager.get_image_path(entity_name, subtype)
        if not image_path or not image_path.exists():
            raise ValueError(f"Image non trouvee: {entity_name}/{subtype}")

        # Marquer comme pret (l'image est valide et accessible)
        ReferenceManager.mark_embedding_cached(entity_name, subtype)

        print(f"✅ Reference validee: {entity_name}/{subtype}")

        return {
            "status": "success",
            "entity": entity_name,
            "subtype": subtype,
        }

    except Exception as exc:
        print(f"❌ Erreur validation {entity_name}/{subtype}: {exc}")
        self.retry(countdown=5, exc=exc)
