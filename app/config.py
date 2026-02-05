import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"
REFERENCE_DIR = BASE_DIR / "reference"

# Nouvelle structure organisée
BASE_MODELS_DIR = MODELS_DIR / "base_models"
LORAS_DIR = MODELS_DIR / "loras"
LORAS_HF_DIR = LORAS_DIR / "huggingface"
LORAS_CIVITAI_DIR = LORAS_DIR / "civitai"
VAE_DIR = MODELS_DIR / "vae"

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# API Tokens (Optional)
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN", None)
CIVITAI_API_TOKEN = os.getenv("CIVITAI_API_TOKEN", None)

# Modèles
SDXL_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
VAE_MODEL = (
    "madebyollin/sdxl-vae-fp16-fix"  # VAE corrigé pour eviter les artefacts noirs
)
IP_ADAPTER_MODEL = "h94/IP-Adapter"
IP_ADAPTER_SUBFOLDER = "sdxl_models"
IP_ADAPTER_WEIGHT = "ip-adapter_sdxl.bin"

# Optimisation 2080 Ti (11Go)
MAX_QUEUE_SIZE = 100
DEFAULT_STEPS = 30
GUIDANCE_SCALE = 7.5
IMAGE_SIZE = (1024, 1024)  # SDXL natif
OFFLOAD_TO_CPU = True  # Critical pour 11Go VRAM

# References
REFERENCE_METADATA_FILE = REFERENCE_DIR / "metadata.json"
REFERENCE_CATEGORIES = ["character", "background", "pose"]
CATEGORY_SUBTYPES = {
    "character": ["front", "side", "back", "full_body", "detail"],
    "background": ["main", "variant"],
    "pose": ["main", "variant"],
}
MAX_REFERENCE_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
