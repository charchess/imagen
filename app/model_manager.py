"""
Gestionnaire de modèles et LoRAs avec support de téléchargement automatique
"""

import logging
import os
import requests
from pathlib import Path
from typing import Optional, Dict, List
from huggingface_hub import hf_hub_download, scan_cache_dir

logger = logging.getLogger(__name__)

from app.config import (
    MODELS_DIR, BASE_MODELS_DIR, LORAS_DIR,
    LORAS_HF_DIR, LORAS_CIVITAI_DIR, VAE_DIR,
    HUGGINGFACE_TOKEN, CIVITAI_API_TOKEN
)


class ModelManager:
    """Gestion des modèles et LoRAs avec téléchargement automatique"""

    @staticmethod
    def is_model_installed(model_path: str, checkpoint_url: Optional[str] = None) -> bool:
        """
        Vérifie si un modèle est installé localement.

        Args:
            model_path: Chemin HuggingFace (ex: "stabilityai/stable-diffusion-xl-base-1.0")
            checkpoint_url: Nom du fichier checkpoint si applicable

        Returns:
            True si le modèle est installé
        """
        try:
            cache_info = scan_cache_dir(MODELS_DIR)

            # Normaliser le model_path pour correspondre au format du cache
            repo_id = model_path.replace("/", "--")
            expected_repo = f"models--{repo_id}"

            # Vérifier si le repo existe dans le cache
            for repo in cache_info.repos:
                if expected_repo in str(repo.repo_path):
                    # Si checkpoint spécifique requis, vérifier sa présence
                    if checkpoint_url:
                        for revision in repo.revisions:
                            for file in revision.files:
                                if checkpoint_url in str(file.file_path):
                                    return True
                        return False
                    # Sinon, vérifier qu'il y a au moins des fichiers
                    return len(list(repo.revisions)) > 0

            return False
        except Exception as e:
            logger.warning("Erreur verification modele %s: %s", model_path, e)
            return False

    @staticmethod
    def is_lora_installed(lora_path: str) -> bool:
        """
        Vérifie si un LoRA est installé localement.

        Args:
            lora_path: Chemin HuggingFace ou local

        Returns:
            True si le LoRA est installé
        """
        # Chemin local (ex: ./models/civitai_618068)
        if lora_path.startswith("./"):
            local_path = Path(lora_path)
            return local_path.exists() and any(local_path.glob("*.safetensors"))

        # Chemin HuggingFace
        return ModelManager.is_model_installed(lora_path)

    @staticmethod
    def download_from_civitai(
        model_id: int,
        output_dir: Path,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Télécharge un modèle/LoRA depuis Civitai.

        Args:
            model_id: ID du modèle sur Civitai
            output_dir: Répertoire de destination
            filename: Nom du fichier de sortie (optionnel)

        Returns:
            Chemin du fichier téléchargé ou None si échec
        """
        try:
            # API Civitai pour obtenir les infos du modèle
            api_url = f"https://civitai.com/api/v1/models/{model_id}"

            headers = {}
            if CIVITAI_API_TOKEN:
                headers["Authorization"] = f"Bearer {CIVITAI_API_TOKEN}"

            logger.info("Recuperation infos Civitai model %d", model_id)
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()

            model_data = response.json()

            # Récupérer la dernière version
            if not model_data.get("modelVersions"):
                logger.error("Aucune version disponible")
                return None

            latest_version = model_data["modelVersions"][0]

            # Trouver le fichier principal (.safetensors)
            download_url = None
            original_filename = None

            for file in latest_version.get("files", []):
                if file.get("primary", False) or file["name"].endswith(".safetensors"):
                    download_url = file["downloadUrl"]
                    original_filename = file["name"]
                    break

            if not download_url:
                logger.error("Aucun fichier telechargeable trouve")
                return None

            # Préparer le téléchargement
            output_dir.mkdir(parents=True, exist_ok=True)
            output_filename = filename or original_filename
            output_path = output_dir / output_filename

            logger.info("Telechargement depuis Civitai: %s", output_filename)
            logger.debug("URL: %s", download_url)

            # Télécharger avec barre de progression
            if CIVITAI_API_TOKEN:
                download_url += f"?token={CIVITAI_API_TOKEN}"

            response = requests.get(download_url, stream=True, headers=headers)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            next_milestone = 25

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if progress >= next_milestone:
                                logger.info("Download progress: %.0f%%", progress)
                                next_milestone += 25

            logger.info("Telecharge: %s", output_path)
            return output_path

        except Exception as e:
            print(f"❌ Erreur téléchargement Civitai {model_id}: {e}")
            return None

    @staticmethod
    def get_installed_models() -> List[Dict]:
        """
        Liste tous les modèles installés dans le cache.

        Returns:
            Liste des modèles avec leurs infos
        """
        installed = []
        try:
            cache_info = scan_cache_dir(MODELS_DIR)

            for repo in cache_info.repos:
                repo_name = str(repo.repo_path.name).replace("models--", "").replace("--", "/")

                # Calculer la taille totale
                total_size = sum(
                    sum(file.size_on_disk for file in revision.files)
                    for revision in repo.revisions
                )

                installed.append({
                    "repo_id": repo_name,
                    "size_gb": round(total_size / (1024**3), 2),
                    "num_files": sum(len(list(rev.files)) for rev in repo.revisions)
                })
        except Exception as e:
            print(f"⚠️  Erreur listage modèles: {e}")

        return installed

    @staticmethod
    def get_installed_loras() -> List[Dict]:
        """
        Liste tous les LoRAs installés (HuggingFace + Civitai).

        Returns:
            Liste des LoRAs avec leurs infos
        """
        installed = []

        # LoRAs Civitai
        if LORAS_CIVITAI_DIR.exists():
            for item in LORAS_CIVITAI_DIR.iterdir():
                if item.is_dir():
                    safetensors = list(item.glob("*.safetensors"))
                    if safetensors:
                        total_size = sum(f.stat().st_size for f in safetensors)
                        installed.append({
                            "source": "civitai",
                            "path": str(item.relative_to(MODELS_DIR.parent)),
                            "size_mb": round(total_size / (1024**2), 1),
                            "files": [f.name for f in safetensors]
                        })

        # LoRAs HuggingFace (dans le cache)
        try:
            cache_info = scan_cache_dir(MODELS_DIR)
            for repo in cache_info.repos:
                repo_name = str(repo.repo_path.name).replace("models--", "").replace("--", "/")
                # Détecter si c'est un LoRA (contient "lora" dans le nom)
                if "lora" in repo_name.lower():
                    total_size = sum(
                        sum(file.size_on_disk for file in revision.files)
                        for revision in repo.revisions
                    )
                    installed.append({
                        "source": "huggingface",
                        "reference": f"huggingface-{repo_name}",
                        "size_mb": round(total_size / (1024**2), 1),
                        "num_files": sum(len(list(rev.files)) for rev in repo.revisions)
                    })
        except Exception as e:
            print(f"⚠️  Erreur scan LoRAs HuggingFace: {e}")

        return installed
