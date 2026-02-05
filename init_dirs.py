#!/usr/bin/env python3
"""
Script d'initialisation de la structure de dossiers pour Imagen
"""

from pathlib import Path
from app.config import (
    MODELS_DIR, BASE_MODELS_DIR, LORAS_DIR,
    LORAS_HF_DIR, LORAS_CIVITAI_DIR, VAE_DIR,
    OUTPUTS_DIR, REFERENCE_DIR
)

def init_directories():
    """Crée la structure de dossiers complète"""

    dirs = [
        MODELS_DIR,
        BASE_MODELS_DIR,
        LORAS_DIR,
        LORAS_HF_DIR,
        LORAS_CIVITAI_DIR,
        VAE_DIR,
        OUTPUTS_DIR,
        REFERENCE_DIR
    ]

    print("🔧 Initialisation de la structure de dossiers...")

    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ {directory}")

    # Créer un .gitkeep dans chaque dossier pour Git
    for directory in dirs:
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    print("\n✨ Structure de dossiers initialisée !")
    print("\n📁 Arborescence créée :")
    print("""
    models/
    ├── base_models/     # Modèles principaux (SDXL, PonyXL)
    ├── loras/
    │   ├── huggingface/ # LoRAs depuis HuggingFace
    │   └── civitai/     # LoRAs depuis Civitai
    ├── vae/             # VAE et composants
    ├── outputs/         # Images générées
    └── reference/       # Images de référence
    """)

if __name__ == "__main__":
    init_directories()
