"""
Pipeline de génération d'images SDXL avec support multi-modèles et LoRA
"""

import gc
import logging
import torch
from diffusers import StableDiffusionXLPipeline, AutoencoderKL
from PIL import Image
from pathlib import Path
from typing import Optional, List, Dict

from app.config import *
from app.models_config import get_model_config, get_lora_config, DEFAULT_MODEL
from compel import Compel, ReturnedEmbeddingsType

# Import tokens from config
from app.config import HUGGINGFACE_TOKEN, CIVITAI_API_TOKEN

logger = logging.getLogger(__name__)


class FlexiblePipeline:
    """Pipeline multi-modèles avec support LoRA/LyCORIS"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FlexiblePipeline, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        logger.info("Initialisation du pipeline flexible")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # État du pipeline
        self.current_model = None
        self.pipe = None
        self.compel = None
        self.loaded_loras = {}  # Track loaded LoRAs
        self.ip_adapter_loaded = False

        # Charger le modèle par défaut
        self.load_model(DEFAULT_MODEL)

        self._initialized = True
        logger.info("Pipeline pret sur %s", self.device)

    def load_model(self, model_id: str):
        """Charge un modèle base (avec lazy loading)"""
        if hasattr(self, 'current_model') and hasattr(self, 'pipe') and \
           self.current_model == model_id and self.pipe is not None:
            logger.debug("Modele %s deja charge", model_id)
            return  # Déjà chargé

        logger.info("Chargement du modele: %s", model_id)

        # Clear previous model
        if hasattr(self, 'pipe') and self.pipe is not None:
            logger.debug("Nettoyage du modele precedent")
            del self.pipe
            del self.compel
            torch.cuda.empty_cache()
            gc.collect()

        # Get model config
        model_config = get_model_config(model_id)
        if not model_config:
            raise ValueError(f"Modèle {model_id} non trouvé dans la configuration")

        # Load pipeline
        logger.info("Chargement de %s", model_config.full_name)

        # Check if it's a checkpoint (single file) or full pipeline
        if model_config.checkpoint_url:
            # Load from checkpoint .safetensors file
            logger.debug("Chargement depuis checkpoint: %s/%s", model_config.path, model_config.checkpoint_url)

            # Build full HuggingFace URL for the checkpoint
            from huggingface_hub import hf_hub_download

            # Download the checkpoint file
            logger.info("Telechargement du checkpoint depuis HuggingFace")
            checkpoint_path = hf_hub_download(
                repo_id=model_config.path,
                filename=model_config.checkpoint_url,
                cache_dir=MODELS_DIR,
                token=HUGGINGFACE_TOKEN if HUGGINGFACE_TOKEN else None
            )

            logger.info("Checkpoint telecharge: %s", checkpoint_path)

            load_kwargs = {
                "torch_dtype": torch.float16,
                "use_safetensors": True
            }

            # Load from the downloaded checkpoint file
            self.pipe = StableDiffusionXLPipeline.from_single_file(
                checkpoint_path,
                **load_kwargs
            )
        else:
            # Load from full diffusers pipeline
            logger.debug("Chargement depuis pipeline diffusers: %s", model_config.path)

            load_kwargs = {
                "torch_dtype": torch.float16,
                "variant": "fp16",
                "use_safetensors": True,
                "cache_dir": MODELS_DIR
            }

            # Add HuggingFace token if available (for gated/private models)
            if HUGGINGFACE_TOKEN:
                load_kwargs["token"] = HUGGINGFACE_TOKEN
                logger.debug("Utilisation du token HuggingFace")

            self.pipe = StableDiffusionXLPipeline.from_pretrained(
                model_config.path,
                **load_kwargs
            )

        # Load custom VAE if specified
        if model_config.vae_path:
            logger.debug("Chargement VAE: %s", model_config.vae_path)

            # Build kwargs for VAE loading
            vae_kwargs = {
                "torch_dtype": torch.float16,
                "cache_dir": MODELS_DIR
            }

            # Add HuggingFace token if available
            if HUGGINGFACE_TOKEN:
                vae_kwargs["token"] = HUGGINGFACE_TOKEN

            vae = AutoencoderKL.from_pretrained(
                model_config.vae_path,
                **vae_kwargs
            )
            self.pipe.vae = vae

        # Setup Compel
        logger.debug("Configuration Compel")
        self.compel = Compel(
            tokenizer=[self.pipe.tokenizer, self.pipe.tokenizer_2],
            text_encoder=[self.pipe.text_encoder, self.pipe.text_encoder_2],
            returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,
            requires_pooled=[False, True]
        )

        # GPU optimizations
        logger.debug("Activation des optimisations GPU")
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_vae_slicing()
        self.pipe.enable_vae_tiling()

        self.current_model = model_id
        self.loaded_loras = {}  # Reset LoRAs when changing model
        self.ip_adapter_loaded = False  # Reset IP-Adapter
        logger.info("Modele %s pret", model_id)

    def load_loras(self, lora_configs: List[Dict]):
        """Charge et fusionne plusieurs LoRAs"""
        if not lora_configs:
            # Unload all LoRAs
            if self.loaded_loras:
                logger.debug("Dechargement des LoRAs")
                self.pipe.unload_lora_weights()
                self.loaded_loras = {}
            return

        # Build LoRA configuration
        adapter_names = []
        adapter_weights = []

        for lora_req in lora_configs:
            lora_id = lora_req["name"]
            weight = lora_req["weight"]

            # Get LoRA config
            lora_config = get_lora_config(lora_id)
            if not lora_config:
                logger.warning("LoRA %s non trouve, ignore", lora_id)
                continue

            # Load LoRA if not already loaded
            if lora_id not in self.loaded_loras:
                logger.info("Chargement LoRA: %s (weight=%s)", lora_config.name, weight)
                try:
                    # Build kwargs for load_lora_weights
                    lora_kwargs = {
                        "adapter_name": lora_id,
                        "cache_dir": MODELS_DIR
                    }

                    # Add HuggingFace token if available
                    if HUGGINGFACE_TOKEN:
                        lora_kwargs["token"] = HUGGINGFACE_TOKEN

                    self.pipe.load_lora_weights(
                        lora_config.path,
                        **lora_kwargs
                    )
                    self.loaded_loras[lora_id] = lora_config
                except Exception as e:
                    logger.error("Erreur chargement LoRA %s", lora_id, exc_info=True)
                    continue

            adapter_names.append(lora_id)
            adapter_weights.append(weight)

        # Set active adapters with weights
        if adapter_names:
            self.pipe.set_adapters(adapter_names, adapter_weights=adapter_weights)
            logger.info("LoRAs actifs: %s", ", ".join(adapter_names))
        else:
            logger.warning("Aucun LoRA charge")

    def enhance_prompt_with_trigger_words(self, prompt: str, lora_configs: List[Dict]) -> str:
        """Ajoute les trigger words des LoRAs au prompt si nécessaire"""
        enhanced_prompt = prompt

        for lora_req in lora_configs:
            lora_config = self.loaded_loras.get(lora_req["name"])
            if lora_config and lora_config.trigger_words:
                # Append trigger words if not already in prompt
                for trigger in lora_config.trigger_words:
                    if trigger.lower() not in prompt.lower():
                        enhanced_prompt += f", {trigger}"

        if enhanced_prompt != prompt:
            logger.debug("Prompt enrichi avec trigger words")

        return enhanced_prompt

    def _ensure_ip_adapter_loaded(self):
        """Charge IP-Adapter Plus si pas deja charge"""
        if not self.ip_adapter_loaded:
            logger.info("Chargement IP-Adapter (%s)", IP_ADAPTER_WEIGHT)
            self.pipe.load_ip_adapter(
                IP_ADAPTER_MODEL,
                subfolder=IP_ADAPTER_SUBFOLDER,
                weight_name=IP_ADAPTER_WEIGHT,
                cache_dir=MODELS_DIR
            )
            self.ip_adapter_loaded = True
            logger.info("IP-Adapter charge")

    def compute_embedding(self, image_path: str) -> torch.Tensor:
        """
        Calcule l'embedding CLIP pour une image de reference.
        Reserve pour usage futur (IP-Adapter Plus avec encodeur ViT-H correct).
        Pour l'instant, les images brutes sont passees directement au pipeline.
        """
        # Pour l'instant, on ne pre-calcule pas d'embeddings.
        # Le pipeline utilise les images brutes directement.
        # Cette methode est gardee pour compatibilite avec compute_embedding_task.
        return torch.zeros(1)  # Placeholder

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = DEFAULT_MODEL,
        loras: List[Dict] = [],
        steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        reference_image_path: Optional[str] = None,
        ip_strength: float = 0.0,
        reference_images: Optional[List[Dict]] = None,
    ):
        """
        Génération avec support multi-modèles, LoRAs et references multiples

        Args:
            prompt: Description de l'image
            negative_prompt: Éléments à éviter
            model: ID du modèle base
            loras: Liste des LoRAs [{name, weight}, ...]
            steps: Nombre d'étapes de diffusion
            guidance_scale: CFG scale
            seed: Seed pour reproductibilité
            reference_image_path: (Legacy) Chemin vers image de référence
            ip_strength: (Legacy) Force du style transfer (0.0-1.0)
            reference_images: Liste de references [{path, strength, embedding_path}, ...]
        """

        try:
            # Memory cleanup
            gc.collect()
            torch.cuda.empty_cache()

            # Load model if needed
            self.load_model(model)

            # Load LoRAs
            self.load_loras(loras)

            # Enhance prompt with trigger words
            enhanced_prompt = self.enhance_prompt_with_trigger_words(prompt, loras)

            logger.debug("Prompt (%d chars)", len(enhanced_prompt))

            # Compel encoding
            conditioning, pooled = self.compel(enhanced_prompt)
            neg_conditioning, neg_pooled = self.compel(negative_prompt) if negative_prompt else (None, None)

            # IP-Adapter avec references multiples
            ip_args = {}

            if reference_images and len(reference_images) > 0:
                self._ensure_ip_adapter_loaded()

                # Calculer la strength moyenne
                avg_strength = sum(r["strength"] for r in reference_images) / len(reference_images)
                self.pipe.set_ip_adapter_scale(avg_strength)

                # Charger les images de reference
                raw_images = []
                for ref in reference_images:
                    if Path(ref["path"]).exists():
                        raw_images.append(Image.open(ref["path"]).convert("RGB"))

                if raw_images:
                    if len(raw_images) == 1:
                        ip_args = {"ip_adapter_image": raw_images[0]}
                    else:
                        ip_args = {"ip_adapter_image": raw_images}
                    logger.info("IP-Adapter: %d reference(s) (strength=%.2f)", len(raw_images), avg_strength)

            elif reference_image_path and Path(reference_image_path).exists() and ip_strength > 0:
                # Legacy: single reference image
                self._ensure_ip_adapter_loaded()

                ref_image = Image.open(reference_image_path).convert("RGB")
                self.pipe.set_ip_adapter_scale(ip_strength)
                ip_args = {"ip_adapter_image": ref_image}
                logger.info("IP-Adapter legacy (strength=%s)", ip_strength)

            # Generator with seed
            generator = None
            if seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)
                logger.debug("Seed: %s", seed)

            logger.info("Generation (steps=%d, cfg=%s)", steps, guidance_scale)

            # Generation
            image = self.pipe(
                prompt_embeds=conditioning,
                pooled_prompt_embeds=pooled,
                negative_prompt_embeds=neg_conditioning,
                negative_pooled_prompt_embeds=neg_pooled,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                generator=generator,
                height=IMAGE_SIZE[1],
                width=IMAGE_SIZE[0],
                **ip_args
            ).images[0]

            torch.cuda.empty_cache()
            logger.info("Generation terminee")
            return image

        except Exception as e:
            logger.error("Generation failed", exc_info=True)
            torch.cuda.empty_cache()
            raise


# Singleton instance
pipeline = FlexiblePipeline()
