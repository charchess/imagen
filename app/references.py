"""
Gestionnaire de references graphiques (personnages, backgrounds, poses)
"""

import fcntl
import json
import shutil
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image
from pydantic import BaseModel, Field

from app.config import (
    CATEGORY_SUBTYPES,
    MAX_REFERENCE_IMAGE_SIZE,
    REFERENCE_CATEGORIES,
    REFERENCE_DIR,
    REFERENCE_METADATA_FILE,
)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Mapping categorie -> sous-dossier
CATEGORY_DIRS = {
    "character": "characters",
    "background": "backgrounds",
    "pose": "poses",
}


# ============================================
# MODELES PYDANTIC
# ============================================


class ReferenceImage(BaseModel):
    filename: str
    original_name: str
    width: int
    height: int
    uploaded_at: str
    embedding_cached: bool = False


class ReferenceEntity(BaseModel):
    category: str
    description: Optional[str] = None
    created_at: str
    references: Dict[str, ReferenceImage] = {}


class ReferenceMetadata(BaseModel):
    version: int = 1
    entities: Dict[str, ReferenceEntity] = {}


class ReferenceRequest(BaseModel):
    """Utilise dans GenerationRequest pour specifier les references"""

    entity: str = Field(description="Nom de l'entite (ex: electra, cuisine)")
    types: List[str] = Field(
        default=["front"], description="Sous-types a utiliser (ex: front, side)"
    )
    strength: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Force du style transfer (0.4-0.6 recommande)",
    )


# ============================================
# REFERENCE MANAGER
# ============================================


class ReferenceManager:
    """Gestionnaire CRUD pour les references graphiques"""

    @staticmethod
    def load_metadata() -> ReferenceMetadata:
        if not REFERENCE_METADATA_FILE.exists():
            return ReferenceMetadata()
        try:
            data = json.loads(REFERENCE_METADATA_FILE.read_text(encoding="utf-8"))
            return ReferenceMetadata(**data)
        except (json.JSONDecodeError, Exception):
            return ReferenceMetadata()

    @staticmethod
    def save_metadata(metadata: ReferenceMetadata) -> None:
        REFERENCE_METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = REFERENCE_METADATA_FILE.with_suffix(".tmp")
        content = json.dumps(metadata.model_dump(), indent=2, ensure_ascii=False)

        with open(tmp_path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(content)
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

        tmp_path.rename(REFERENCE_METADATA_FILE)

    @staticmethod
    def _entity_dir(category: str, entity_name: str) -> Path:
        subdir = CATEGORY_DIRS.get(category, category)
        return REFERENCE_DIR / subdir / entity_name

    @staticmethod
    def create_entity(
        name: str, category: str, description: Optional[str] = None
    ) -> ReferenceEntity:
        if category not in REFERENCE_CATEGORIES:
            raise ValueError(
                f"Categorie invalide '{category}'. "
                f"Utiliser: {', '.join(REFERENCE_CATEGORIES)}"
            )

        metadata = ReferenceManager.load_metadata()

        if name in metadata.entities:
            raise ValueError(f"L'entite '{name}' existe deja")

        entity_dir = ReferenceManager._entity_dir(category, name)
        entity_dir.mkdir(parents=True, exist_ok=True)

        entity = ReferenceEntity(
            category=category,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        metadata.entities[name] = entity
        ReferenceManager.save_metadata(metadata)

        return entity

    @staticmethod
    def upload_image(
        entity_name: str,
        subtype: str,
        image_data: bytes,
        original_filename: str,
    ) -> ReferenceImage:
        metadata = ReferenceManager.load_metadata()

        if entity_name not in metadata.entities:
            raise ValueError(f"Entite '{entity_name}' non trouvee")

        entity = metadata.entities[entity_name]

        allowed_subtypes = CATEGORY_SUBTYPES.get(entity.category, [])
        if subtype not in allowed_subtypes:
            raise ValueError(
                f"Sous-type '{subtype}' invalide pour categorie '{entity.category}'. "
                f"Utiliser: {', '.join(allowed_subtypes)}"
            )

        if len(image_data) > MAX_REFERENCE_IMAGE_SIZE:
            raise ValueError(
                f"Fichier trop volumineux ({len(image_data) // (1024*1024)}MB). "
                f"Max {MAX_REFERENCE_IMAGE_SIZE // (1024*1024)}MB"
            )

        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Format '{ext}' non supporte. "
                f"Utiliser: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Ouvrir, convertir RGB, resize 1024x1024 (center-crop)
        try:
            img = Image.open(BytesIO(image_data)).convert("RGB")
        except Exception:
            raise ValueError("Impossible de lire l'image. Fichier corrompu ?")

        img = _center_crop_resize(img, 1024, 1024)

        # Sauvegarder
        entity_dir = ReferenceManager._entity_dir(entity.category, entity_name)
        entity_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{subtype}.png"
        filepath = entity_dir / filename
        img.save(filepath, "PNG")

        # Supprimer embedding cache si existant (sera recalcule)
        embedding_path = entity_dir / f"{subtype}.pt"
        if embedding_path.exists():
            embedding_path.unlink()

        ref_image = ReferenceImage(
            filename=filename,
            original_name=original_filename,
            width=img.width,
            height=img.height,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            embedding_cached=False,
        )

        entity.references[subtype] = ref_image
        ReferenceManager.save_metadata(metadata)

        return ref_image

    @staticmethod
    def delete_entity(name: str) -> int:
        metadata = ReferenceManager.load_metadata()

        if name not in metadata.entities:
            raise ValueError(f"Entite '{name}' non trouvee")

        entity = metadata.entities[name]
        entity_dir = ReferenceManager._entity_dir(entity.category, name)
        images_count = len(entity.references)

        if entity_dir.exists():
            shutil.rmtree(entity_dir)

        del metadata.entities[name]
        ReferenceManager.save_metadata(metadata)

        return images_count

    @staticmethod
    def delete_image(entity_name: str, subtype: str) -> None:
        metadata = ReferenceManager.load_metadata()

        if entity_name not in metadata.entities:
            raise ValueError(f"Entite '{entity_name}' non trouvee")

        entity = metadata.entities[entity_name]

        if subtype not in entity.references:
            raise ValueError(
                f"Sous-type '{subtype}' non trouve pour '{entity_name}'"
            )

        entity_dir = ReferenceManager._entity_dir(entity.category, entity_name)

        # Supprimer image + embedding
        image_path = entity_dir / entity.references[subtype].filename
        if image_path.exists():
            image_path.unlink()

        embedding_path = entity_dir / f"{subtype}.pt"
        if embedding_path.exists():
            embedding_path.unlink()

        del entity.references[subtype]
        ReferenceManager.save_metadata(metadata)

    @staticmethod
    def list_entities(
        category: Optional[str] = None,
    ) -> Dict[str, ReferenceEntity]:
        metadata = ReferenceManager.load_metadata()

        if category is None:
            return metadata.entities

        return {
            name: entity
            for name, entity in metadata.entities.items()
            if entity.category == category
        }

    @staticmethod
    def get_entity(name: str) -> Optional[ReferenceEntity]:
        metadata = ReferenceManager.load_metadata()
        return metadata.entities.get(name)

    @staticmethod
    def resolve_references(
        refs: List[ReferenceRequest],
    ) -> List[Dict]:
        """
        Resout les references en chemins fichiers.

        Returns:
            List de dicts: [{"path": str, "strength": float, "embedding_path": str|None, "category": str}]

        Raises:
            ValueError si une reference est manquante ou embeddings pas prets.
        """
        metadata = ReferenceManager.load_metadata()
        resolved = []

        for ref in refs:
            if ref.entity not in metadata.entities:
                raise ValueError(f"Reference '{ref.entity}' non trouvee")

            entity = metadata.entities[ref.entity]

            for subtype in ref.types:
                if subtype not in entity.references:
                    raise ValueError(
                        f"Type '{subtype}' non trouve pour '{ref.entity}'. "
                        f"Disponibles: {list(entity.references.keys())}"
                    )

                ref_image = entity.references[subtype]
                entity_dir = ReferenceManager._entity_dir(
                    entity.category, ref.entity
                )
                image_path = entity_dir / ref_image.filename
                embedding_path = entity_dir / f"{subtype}.pt"

                if not image_path.exists():
                    raise ValueError(
                        f"Fichier image manquant pour {ref.entity}/{subtype}"
                    )

                resolved.append(
                    {
                        "path": str(image_path),
                        "strength": ref.strength,
                        "embedding_path": str(embedding_path)
                        if embedding_path.exists()
                        else None,
                        "category": entity.category,
                    }
                )

        return resolved

    @staticmethod
    def mark_embedding_cached(entity_name: str, subtype: str) -> None:
        metadata = ReferenceManager.load_metadata()
        if entity_name in metadata.entities:
            entity = metadata.entities[entity_name]
            if subtype in entity.references:
                entity.references[subtype].embedding_cached = True
                ReferenceManager.save_metadata(metadata)

    @staticmethod
    def get_image_path(entity_name: str, subtype: str) -> Optional[Path]:
        metadata = ReferenceManager.load_metadata()
        if entity_name not in metadata.entities:
            return None
        entity = metadata.entities[entity_name]
        if subtype not in entity.references:
            return None
        entity_dir = ReferenceManager._entity_dir(entity.category, entity_name)
        return entity_dir / entity.references[subtype].filename

    @staticmethod
    def get_embedding_path(entity_name: str, subtype: str) -> Optional[Path]:
        metadata = ReferenceManager.load_metadata()
        if entity_name not in metadata.entities:
            return None
        entity = metadata.entities[entity_name]
        if subtype not in entity.references:
            return None
        entity_dir = ReferenceManager._entity_dir(entity.category, entity_name)
        path = entity_dir / f"{subtype}.pt"
        return path if path.exists() else None


# ============================================
# UTILITAIRES
# ============================================


def _center_crop_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Redimensionne en center-crop pour atteindre target_w x target_h"""
    w, h = img.size
    target_ratio = target_w / target_h
    img_ratio = w / h

    if img_ratio > target_ratio:
        # Image trop large -> crop horizontal
        new_w = int(h * target_ratio)
        offset = (w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, h))
    elif img_ratio < target_ratio:
        # Image trop haute -> crop vertical
        new_h = int(w / target_ratio)
        offset = (h - new_h) // 2
        img = img.crop((0, offset, w, offset + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)
