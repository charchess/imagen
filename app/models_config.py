"""
Configuration des modèles et LoRAs disponibles
"""

from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel


class LoRAConfig(BaseModel):
    """Configuration d'un LoRA"""
    name: str  # Nom descriptif complet
    reference: str  # Référence unique (civitai-123456, huggingface-org/model)
    path: str  # Chemin de stockage
    source: str  # "civitai" ou "huggingface"
    default_weight: float = 0.8
    trigger_words: Optional[List[str]] = None
    description: Optional[str] = None


class ModelConfig(BaseModel):
    """Configuration d'un modèle base"""
    short_name: str  # Nom court (sdxl, pony)
    full_name: str  # Nom complet (Stable Diffusion XL Base 1.0)
    path: str  # Chemin HuggingFace ou local
    vae_path: Optional[str] = None
    supported_loras: List[str] = []
    default_negative: str = ""
    description: Optional[str] = None
    checkpoint_url: Optional[str] = None  # URL du checkpoint .safetensors (si applicable)


# ============================================
# MODÈLES DISPONIBLES
# ============================================

AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    "sdxl": ModelConfig(
        short_name="SDXL",
        full_name="Stable Diffusion XL Base 1.0",
        path="stabilityai/stable-diffusion-xl-base-1.0",
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        default_negative="low quality, blurry, distorted, ugly, bad anatomy",
        description="Modèle base polyvalent pour génération réaliste"
    ),

    "pony": ModelConfig(
        short_name="Pony",
        full_name="Pony Diffusion V6 XL",
        path="LyliaEngine/Pony_Diffusion_V6_XL",
        checkpoint_url="ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        supported_loras=["anime-style", "character-detail", "civitai-618068"],
        default_negative="low quality, bad anatomy, worst quality, low res",
        description="Fine-tuné pour style anime/furry avec personnages anthropomorphes"
    ),
}

# Modèle par défaut
DEFAULT_MODEL = "sdxl"


# ============================================
# LORAs DISPONIBLES
# ============================================

AVAILABLE_LORAS: Dict[str, LoRAConfig] = {
    "anime-style": LoRAConfig(
        name="Anime Style Enhancer",
        reference="huggingface-Linaqruf/anime-detailer-xl-lora",
        path="Linaqruf/anime-detailer-xl-lora",
        source="huggingface",
        default_weight=0.75,
        trigger_words=["anime style", "detailed"],
        description="Améliore le style anime et les détails des illustrations"
    ),

    "character-detail": LoRAConfig(
        name="Character Detail Enhancement",
        reference="huggingface-Lykon/character-detail-lora-xl",
        path="Lykon/character-detail-lora-xl",
        source="huggingface",
        default_weight=0.6,
        trigger_words=None,
        description="Améliore les détails des personnages (visage, yeux, expressions)"
    ),

    "civitai-618068": LoRAConfig(
        name="Pony Realism V2.0",
        reference="civitai-618068",
        path="./models/loras/civitai/civitai_618068",
        source="civitai",
        default_weight=0.8,
        trigger_words=None,
        description="Style réaliste pour PonyXL (exemple Civitai)"
    ),
}


# ============================================
# LYCORIs DISPONIBLES (structure identique)
# ============================================

AVAILABLE_LYCORIS: Dict[str, LoRAConfig] = {
    # "cyberpunk-style": LoRAConfig(
    #     name="Cyberpunk LyCORIS",
    #     path="artificialguybr/cyberpunk-lycoris-xl",
    #     default_weight=0.8,
    #     trigger_words=["cyberpunk", "neon"],
    #     description="Style cyberpunk avec néons"
    # ),
}


# ============================================
# HELPERS
# ============================================

def get_all_loras() -> Dict[str, LoRAConfig]:
    """Retourne tous les LoRAs et LyCORIS disponibles"""
    return {**AVAILABLE_LORAS, **AVAILABLE_LYCORIS}


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """Récupère la config d'un modèle par ID"""
    return AVAILABLE_MODELS.get(model_id)


def get_lora_config(lora_id: str) -> Optional[LoRAConfig]:
    """Récupère la config d'un LoRA par ID"""
    all_loras = get_all_loras()
    return all_loras.get(lora_id)


def list_available_models() -> List[str]:
    """Liste les IDs des modèles disponibles"""
    return list(AVAILABLE_MODELS.keys())


def list_available_loras() -> List[str]:
    """Liste les IDs des LoRAs disponibles"""
    return list(get_all_loras().keys())
