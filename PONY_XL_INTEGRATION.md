# 🦄 PonyXL v6 + LoRA/LyCORIS Integration

> Architecture pour modèles multiples et adapters dynamiques

---

## 📋 Architecture Proposée

### 1. Structure de Configuration

```python
# app/models_config.py (NOUVEAU)

from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

class LoRAConfig(BaseModel):
    """Configuration d'un LoRA"""
    name: str
    path: str  # HuggingFace ID ou chemin local
    default_weight: float = 0.8
    trigger_words: Optional[List[str]] = None

class ModelConfig(BaseModel):
    """Configuration d'un modèle base"""
    name: str
    path: str
    vae_path: Optional[str] = None
    supported_loras: List[str] = []
    default_negative: str = ""

# Catalogue de modèles disponibles
AVAILABLE_MODELS = {
    "sdxl-base": ModelConfig(
        name="SDXL Base 1.0",
        path="stabilityai/stable-diffusion-xl-base-1.0",
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        default_negative="low quality, blurry, distorted"
    ),

    "pony-xl-v6": ModelConfig(
        name="PonyXL v6",
        path="AstraliteHeart/pony-diffusion-v6-xl",  # Exemple
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        supported_loras=["style-anime", "character-detailed"],
        default_negative="low quality, bad anatomy, worst quality, low res"
    ),

    # Ajouter d'autres modèles facilement
}

# Catalogue de LoRAs disponibles
AVAILABLE_LORAS = {
    "style-anime": LoRAConfig(
        name="Anime Style LoRA",
        path="Linaqruf/anime-detailer-xl-lora",
        default_weight=0.75,
        trigger_words=["anime style", "detailed"]
    ),

    "character-detailed": LoRAConfig(
        name="Character Detail Enhancement",
        path="Lykon/character-detail-lora-xl",
        default_weight=0.6
    ),

    # Ajouter d'autres LoRAs
}

# LyCORIS (Similar structure)
AVAILABLE_LYCORIS = {
    "cyberpunk-style": LoRAConfig(  # LyCORIS use same structure
        name="Cyberpunk LyCORIS",
        path="artificialguybr/cyberpunk-lycoris",
        default_weight=0.8,
        trigger_words=["cyberpunk", "neon"]
    )
}
```

---

### 2. API Request Schema (Étendu)

```python
# app/api.py (MODIFIÉ)

from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class LoRARequest(BaseModel):
    """Configuration d'un LoRA pour la génération"""
    name: str  # ID du LoRA (de AVAILABLE_LORAS)
    weight: float = Field(default=0.8, ge=0.0, le=2.0)

class GenerationRequest(BaseModel):
    # Paramètres existants
    prompt: str
    negative_prompt: Optional[str] = None  # Devient optionnel
    ip_strength: float = 0.0

    # NOUVEAUX paramètres
    model: str = Field(default="sdxl-base", description="ID du modèle base")
    loras: List[LoRARequest] = Field(default=[], description="Liste des LoRAs à appliquer")
    steps: int = Field(default=30, ge=10, le=100)
    guidance_scale: float = Field(default=7.5, ge=1.0, le=30.0)
    seed: Optional[int] = Field(default=None, description="Seed pour reproductibilité")

    # Validation
    def __init__(self, **data):
        super().__init__(**data)
        # Auto-set negative prompt si non fourni
        if self.negative_prompt is None:
            model_config = AVAILABLE_MODELS.get(self.model)
            if model_config:
                self.negative_prompt = model_config.default_negative
```

---

### 3. Pipeline Flexible (Refactorisé)

```python
# app/pipeline.py (REFACTORISÉ)

import gc
import torch
from diffusers import StableDiffusionXLPipeline, AutoencoderKL
from compel import Compel, ReturnedEmbeddingsType
from pathlib import Path
from typing import Optional, List, Dict

class FlexiblePipeline:
    """Pipeline multi-modèles avec support LoRA/LyCORIS"""

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.current_model = None
        self.pipe = None
        self.compel = None
        self.loaded_loras = {}  # Track loaded LoRAs

    def load_model(self, model_id: str):
        """Charge un modèle base (lazy loading)"""
        if self.current_model == model_id and self.pipe is not None:
            return  # Déjà chargé

        print(f"🔄 Switching to model: {model_id}")

        # Clear previous model
        if self.pipe is not None:
            del self.pipe
            del self.compel
            torch.cuda.empty_cache()
            gc.collect()

        # Get model config
        model_config = AVAILABLE_MODELS[model_id]

        # Load pipeline
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            model_config.path,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
            cache_dir=MODELS_DIR
        )

        # Load custom VAE if specified
        if model_config.vae_path:
            vae = AutoencoderKL.from_pretrained(
                model_config.vae_path,
                torch_dtype=torch.float16,
                cache_dir=MODELS_DIR
            )
            self.pipe.vae = vae

        # Setup Compel
        self.compel = Compel(
            tokenizer=[self.pipe.tokenizer, self.pipe.tokenizer_2],
            text_encoder=[self.pipe.text_encoder, self.pipe.text_encoder_2],
            returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,
            requires_pooled=[False, True]
        )

        # GPU optimizations
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_vae_slicing()
        self.pipe.enable_vae_tiling()

        self.current_model = model_id
        self.loaded_loras = {}  # Reset LoRAs when changing model
        print(f"✅ Model {model_id} ready")

    def load_loras(self, lora_configs: List[Dict]):
        """Charge et fusionne plusieurs LoRAs"""
        if not lora_configs:
            # Unload all LoRAs
            if self.loaded_loras:
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
            lora_config = AVAILABLE_LORAS.get(lora_id) or AVAILABLE_LYCORIS.get(lora_id)
            if not lora_config:
                print(f"⚠️ LoRA {lora_id} not found, skipping")
                continue

            # Load LoRA if not already loaded
            if lora_id not in self.loaded_loras:
                print(f"⬇️ Loading LoRA: {lora_config.name}")
                self.pipe.load_lora_weights(
                    lora_config.path,
                    adapter_name=lora_id,
                    cache_dir=MODELS_DIR
                )
                self.loaded_loras[lora_id] = lora_config

            adapter_names.append(lora_id)
            adapter_weights.append(weight)

        # Set active adapters with weights
        if adapter_names:
            self.pipe.set_adapters(adapter_names, adapter_weights=adapter_weights)
            print(f"✅ Active LoRAs: {', '.join(adapter_names)}")

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = "sdxl-base",
        loras: List[Dict] = [],
        steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        reference_image_path: Optional[str] = None,
        ip_strength: float = 0.0
    ):
        """Génération avec support multi-modèles et LoRAs"""

        try:
            # Memory cleanup
            gc.collect()
            torch.cuda.empty_cache()

            # Load model if needed
            self.load_model(model)

            # Load LoRAs
            self.load_loras(loras)

            # Add LoRA trigger words to prompt if needed
            enhanced_prompt = prompt
            for lora_req in loras:
                lora_config = self.loaded_loras.get(lora_req["name"])
                if lora_config and lora_config.trigger_words:
                    # Append trigger words if not already in prompt
                    for trigger in lora_config.trigger_words:
                        if trigger.lower() not in prompt.lower():
                            enhanced_prompt += f", {trigger}"

            print(f"📝 Prompt: {enhanced_prompt[:100]}...")

            # Compel encoding
            conditioning, pooled = self.compel(enhanced_prompt)
            neg_conditioning, neg_pooled = self.compel(negative_prompt) if negative_prompt else (None, None)

            # IP-Adapter (if needed)
            ip_args = {}
            if reference_image_path and Path(reference_image_path).exists() and ip_strength > 0:
                from PIL import Image
                ref_image = Image.open(reference_image_path).convert("RGB")

                if not hasattr(self, 'ip_adapter_loaded'):
                    print("⬇️ Loading IP-Adapter...")
                    self.pipe.load_ip_adapter(
                        IP_ADAPTER_MODEL,
                        subfolder=IP_ADAPTER_SUBFOLDER,
                        weight_name=IP_ADAPTER_WEIGHT,
                        cache_dir=MODELS_DIR
                    )
                    self.ip_adapter_loaded = True

                self.pipe.set_ip_adapter_scale(ip_strength)
                ip_args = {"ip_adapter_image": ref_image}

            # Generator with seed
            generator = None
            if seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)
                print(f"🎲 Seed: {seed}")

            print(f"🎨 Generating (steps={steps}, cfg={guidance_scale})...")

            # Generation
            image = self.pipe(
                prompt_embeds=conditioning,
                pooled_prompt_embeds=pooled,
                negative_prompt_embeds=neg_conditioning,
                negative_pooled_prompt_embeds=neg_pooled,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                generator=generator,
                height=1024,
                width=1024,
                **ip_args
            ).images[0]

            torch.cuda.empty_cache()
            return image

        except Exception as e:
            print(f"❌ Error: {e}")
            torch.cuda.empty_cache()
            raise

# Singleton instance
pipeline = FlexiblePipeline()
```

---

### 4. Worker Task (Mis à Jour)

```python
# app/worker.py (MODIFIÉ)

@celery_app.task(bind=True, max_retries=3)
def generate_image_task(
    self,
    prompt: str,
    negative_prompt: str = "",
    model: str = "sdxl-base",
    loras: List[Dict] = [],
    steps: int = 30,
    guidance_scale: float = 7.5,
    seed: Optional[int] = None,
    ip_strength: float = 0.0
):
    """Task avec support multi-modèles et LoRAs"""

    try:
        # Update state
        self.update_state(state="PROGRESS", meta={"status": "initializing"})

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        # Add model name to filename
        model_prefix = model.replace("-", "_")
        filename = f"{model_prefix}_{timestamp}_{unique_id}.png"
        output_path = OUTPUTS_DIR / filename

        # Load reference image
        reference_path = str(REFERENCE_IMAGE) if REFERENCE_IMAGE.exists() else None

        # Generate
        image = pipeline.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            loras=loras,
            steps=steps,
            guidance_scale=guidance_scale,
            seed=seed,
            reference_image_path=reference_path,
            ip_strength=ip_strength
        )

        # Save
        image.save(output_path)
        print(f"✅ Image saved: {filename}")

        # Cleanup
        gc.collect()
        torch.cuda.empty_cache()

        return {
            "status": "success",
            "filename": filename,
            "path": str(output_path),
            "url": f"/outputs/{filename}",
            "metadata": {
                "model": model,
                "loras": loras,
                "steps": steps,
                "guidance_scale": guidance_scale,
                "seed": seed
            }
        }

    except Exception as e:
        # Retry logic
        raise self.retry(exc=e, countdown=10)
```

---

## 📊 Exemples d'Utilisation API

### Exemple 1 : PonyXL v6 Simple

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "pony-xl-v6",
    "prompt": "a cute pony character in anime style, detailed eyes, colorful mane",
    "steps": 30,
    "guidance_scale": 7.5
  }'
```

### Exemple 2 : PonyXL + LoRA Anime

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "pony-xl-v6",
    "prompt": "beautiful anime girl with long hair, detailed face, fantasy background",
    "loras": [
      {
        "name": "style-anime",
        "weight": 0.75
      }
    ],
    "steps": 35,
    "guidance_scale": 8.0,
    "seed": 42
  }'
```

### Exemple 3 : Multi-LoRA Stack

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "pony-xl-v6",
    "prompt": "cyberpunk character with neon outfit, detailed face and clothing",
    "loras": [
      {
        "name": "style-anime",
        "weight": 0.6
      },
      {
        "name": "character-detailed",
        "weight": 0.8
      },
      {
        "name": "cyberpunk-style",
        "weight": 0.7
      }
    ],
    "steps": 40,
    "guidance_scale": 7.5
  }'
```

### Exemple 4 : Seed pour Reproductibilité

```bash
# Génération 1
curl -X POST http://localhost:8009/generate \
  -d '{"model": "pony-xl-v6", "prompt": "test", "seed": 12345}'

# Génération 2 (identique à #1)
curl -X POST http://localhost:8009/generate \
  -d '{"model": "pony-xl-v6", "prompt": "test", "seed": 12345}'
```

---

## 🔧 Configuration & Installation

### 1. Mise à Jour des Dépendances

```bash
# requirements.txt (AJOUTER)
peft>=0.7.0  # Pour LoRA
lycoris-lora>=1.0.0  # Pour LyCORIS
```

### 2. Téléchargement des Modèles

```python
# download_models.py (METTRE À JOUR)

from huggingface_hub import snapshot_download

# PonyXL v6
snapshot_download(
    repo_id="AstraliteHeart/pony-diffusion-v6-xl",
    cache_dir="./models"
)

# LoRAs
snapshot_download(
    repo_id="Linaqruf/anime-detailer-xl-lora",
    cache_dir="./models"
)
```

### 3. API Endpoints (Nouveau)

```python
# app/api.py (AJOUTER)

@app.get("/models")
async def list_models():
    """Liste les modèles disponibles"""
    return {
        "models": [
            {
                "id": k,
                "name": v.name,
                "supported_loras": v.supported_loras
            }
            for k, v in AVAILABLE_MODELS.items()
        ]
    }

@app.get("/loras")
async def list_loras():
    """Liste les LoRAs disponibles"""
    all_loras = {**AVAILABLE_LORAS, **AVAILABLE_LYCORIS}
    return {
        "loras": [
            {
                "id": k,
                "name": v.name,
                "default_weight": v.default_weight,
                "trigger_words": v.trigger_words
            }
            for k, v in all_loras.items()
        ]
    }
```

---

## 📈 Migration Path

### Phase 1 : Infrastructure (Semaine 1)
- ✅ Créer `models_config.py`
- ✅ Refactoriser `pipeline.py` → `FlexiblePipeline`
- ✅ Mettre à jour API schema
- ✅ Tests unitaires

### Phase 2 : PonyXL (Semaine 2)
- ✅ Télécharger PonyXL v6
- ✅ Configuration modèle
- ✅ Tests de génération
- ✅ Comparaison SDXL vs Pony

### Phase 3 : LoRA/LyCORIS (Semaine 3)
- ✅ Implémenter chargement LoRA
- ✅ Multi-LoRA stacking
- ✅ Trigger words auto-injection
- ✅ Tests avec différents LoRAs

### Phase 4 : Production (Semaine 4)
- ✅ Documentation API
- ✅ Exemples clients
- ✅ Monitoring VRAM
- ✅ Optimisations performance

---

## ⚠️ Considérations Techniques

### VRAM avec LoRAs

```
SDXL Base seul          : 6.5 GB
+ 1 LoRA                : +0.3 GB
+ 3 LoRAs simultanés    : +0.8 GB
+ IP-Adapter            : +0.5 GB
─────────────────────────────────
Total (pire cas)        : ~8.1 GB ✅

Marge RTX 2080 Ti       : 11 - 8.1 = 2.9 GB ✅
```

### Performance

- **Switching models** : ~30s (déchargement + chargement)
- **Loading LoRA** : ~2-3s par LoRA
- **Génération** : ~4-5 min (inchangé)

**Recommandation** : Implémenter cache de modèle pour éviter switching fréquent.

---

## 🎯 Résumé

### Avantages

✅ **Flexibilité** : Multiples modèles supportés
✅ **Extensibilité** : Ajouter LoRAs facilement via config
✅ **API-driven** : Configuration complète par requête
✅ **Backward compatible** : SDXL base reste par défaut
✅ **Reproductible** : Seeds pour générations identiques
✅ **Multi-LoRA** : Stack jusqu'à 3-4 LoRAs simultanément

### Limitations

⚠️ **VRAM** : Limite à ~3-4 LoRAs simultanés
⚠️ **Switching** : 30s de latence au changement de modèle
⚠️ **Storage** : +10-15 GB par modèle additionnel

---

**Ready to implement!** 🚀
