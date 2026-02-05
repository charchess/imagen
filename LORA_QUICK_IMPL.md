# 🚀 LoRA Quick Implementation Guide

> Implémentation rapide du support LoRA pour SDXL (version light)

---

## 🎯 Objectif

Ajouter le support LoRA à l'API existante **sans refactoring majeur**.

### Features
- ✅ Chargement de LoRAs locaux ou HuggingFace
- ✅ Configuration via API (liste de LoRAs avec poids)
- ✅ Paramètres avancés (steps, cfg, seed)
- ✅ Backward compatible (SDXL base reste par défaut)

---

## 📝 Étapes d'Implémentation

### 1. Mettre à Jour requirements.txt

```bash
# Ajouter à requirements.txt
peft>=0.7.0  # Support LoRA
```

### 2. Modifier API Schema (app/api.py)

```python
from typing import Optional, List
from pydantic import BaseModel, Field

class LoRARequest(BaseModel):
    """Configuration d'un LoRA"""
    path: str  # HuggingFace ID ou chemin local
    weight: float = Field(default=0.8, ge=0.0, le=2.0)
    adapter_name: Optional[str] = None  # Auto-généré si None

class GenerationRequest(BaseModel):
    prompt: str
    negative_prompt: str = "low quality, blurry, distorted"
    ip_strength: float = 0.0

    # NOUVEAUX paramètres
    loras: List[LoRARequest] = Field(default=[], description="Liste des LoRAs")
    steps: int = Field(default=30, ge=10, le=100)
    guidance_scale: float = Field(default=7.5, ge=1.0, le=30.0)
    seed: Optional[int] = None
```

### 3. Modifier pipeline.py

```python
# Ajouter à ElectraPipeline

def load_loras(self, loras: List[Dict]):
    """Charge et applique des LoRAs"""
    if not loras:
        # Unload LoRAs si liste vide
        if hasattr(self, '_loras_loaded') and self._loras_loaded:
            self.pipe.unload_lora_weights()
            self._loras_loaded = False
        return

    adapter_names = []
    adapter_weights = []

    for i, lora in enumerate(loras):
        adapter_name = lora.get('adapter_name') or f"lora_{i}"
        weight = lora.get('weight', 0.8)
        path = lora['path']

        print(f"⬇️ Loading LoRA: {path} (weight={weight})")

        # Load LoRA
        self.pipe.load_lora_weights(
            path,
            adapter_name=adapter_name,
            cache_dir=MODELS_DIR
        )

        adapter_names.append(adapter_name)
        adapter_weights.append(weight)

    # Set adapters
    self.pipe.set_adapters(adapter_names, adapter_weights=adapter_weights)
    self._loras_loaded = True
    print(f"✅ Loaded {len(adapter_names)} LoRAs")

def generate(self, prompt: str, negative_prompt: str = "",
             loras: List[Dict] = [], steps: int = 30,
             guidance_scale: float = 7.5, seed: Optional[int] = None,
             reference_image_path: str = None, ip_strength: float = 0.0):
    """Génération avec support LoRA"""

    try:
        gc.collect()
        torch.cuda.empty_cache()

        # Load LoRAs
        self.load_loras(loras)

        # ... (rest of existing code)

        # Add generator with seed
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)

        # Generation avec nouveaux paramètres
        image = self.pipe(
            prompt_embeds=conditioning,
            pooled_prompt_embeds=pooled,
            negative_prompt_embeds=neg_conditioning,
            negative_pooled_prompt_embeds=neg_pooled,
            num_inference_steps=steps,  # ← Configurable
            guidance_scale=guidance_scale,  # ← Configurable
            generator=generator,  # ← Seed
            height=IMAGE_SIZE[1],
            width=IMAGE_SIZE[0],
            **ip_args
        ).images[0]

        # Cleanup
        torch.cuda.empty_cache()
        return image
```

### 4. Modifier worker.py

```python
@celery_app.task(bind=True, max_retries=3)
def generate_image_task(
    self,
    prompt: str,
    negative_prompt: str = "",
    loras: List[Dict] = [],
    steps: int = 30,
    guidance_scale: float = 7.5,
    seed: Optional[int] = None,
    ip_strength: float = 0.0
):
    """Task avec support LoRA"""

    # ... (existing code)

    image = pipeline.generate(
        prompt=prompt,
        negative_prompt=negative_prompt,
        loras=loras,  # ← Nouveau
        steps=steps,  # ← Nouveau
        guidance_scale=guidance_scale,  # ← Nouveau
        seed=seed,  # ← Nouveau
        reference_image_path=reference_path,
        ip_strength=ip_strength
    )

    # Save result avec metadata
    return {
        "status": "success",
        "filename": filename,
        "path": str(output_path),
        "url": f"/outputs/{filename}",
        "metadata": {
            "loras": loras,
            "steps": steps,
            "guidance_scale": guidance_scale,
            "seed": seed
        }
    }
```

### 5. Modifier API endpoint (app/api.py)

```python
@app.post("/generate", response_model=GenerationResponse)
async def create_generation_task(request: GenerationRequest):
    # ... (existing validation)

    # Soumission avec nouveaux paramètres
    task = generate_image_task.delay(
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        loras=[lora.dict() for lora in request.loras],  # ← Nouveau
        steps=request.steps,  # ← Nouveau
        guidance_scale=request.guidance_scale,  # ← Nouveau
        seed=request.seed,  # ← Nouveau
        ip_strength=request.ip_strength,
    )

    # ... (rest)
```

---

## 🧪 Exemples d'Utilisation

### Exemple 1 : LoRA depuis HuggingFace

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a beautiful anime character with detailed eyes",
    "negative_prompt": "blurry, low quality",
    "loras": [
      {
        "path": "Linaqruf/anime-detailer-xl-lora",
        "weight": 0.75
      }
    ],
    "steps": 35,
    "guidance_scale": 8.0,
    "seed": 42
  }'
```

### Exemple 2 : LoRA local

```bash
# 1. Placer le LoRA dans ./models/my_lora/
# 2. Utiliser

curl -X POST http://localhost:8009/generate \
  -d '{
    "prompt": "test",
    "loras": [
      {
        "path": "./models/my_lora",
        "weight": 0.8
      }
    ]
  }'
```

### Exemple 3 : Multi-LoRA

```bash
curl -X POST http://localhost:8009/generate \
  -d '{
    "prompt": "cyberpunk character",
    "loras": [
      {
        "path": "Linaqruf/anime-detailer-xl-lora",
        "weight": 0.6,
        "adapter_name": "anime"
      },
      {
        "path": "artificialguybr/cyberpunk-lora-xl",
        "weight": 0.8,
        "adapter_name": "cyberpunk"
      }
    ],
    "steps": 40,
    "seed": 12345
  }'
```

---

## 🚀 Déploiement

```bash
# 1. Mettre à jour requirements
pip install peft>=0.7.0

# 2. Rebuild containers
docker-compose down
docker-compose build
docker-compose up -d

# 3. Tester
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "test with default params"
  }'
```

---

## ⚠️ Limitations Version Light

1. **Pas de catalogue** : Pas d'endpoint `/loras` pour lister
2. **Pas de multi-modèles** : Seulement SDXL base pour l'instant
3. **Pas de trigger words** : À ajouter manuellement au prompt
4. **VRAM** : Limite ~3-4 LoRAs simultanés (11GB GPU)

---

## 🔄 Migration vers Version Complète

Cette version light est compatible avec la version complète de [PONY_XL_INTEGRATION.md](PONY_XL_INTEGRATION.md).

Migration path :
1. ✅ Version light (cette implémentation)
2. Ajouter catalogue LoRA (config.py)
3. Ajouter multi-modèles (PonyXL, etc.)
4. Ajouter endpoints `/models` et `/loras`

---

**Temps d'implémentation** : ~1-2 heures
**Complexité** : Moyenne
**Breaking changes** : Non (backward compatible)
