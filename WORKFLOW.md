# 🎨 Imagen - Workflow de Génération d'Images

> Documentation technique complète du pipeline de génération SDXL
>
> **Version** : 1.0 | **Date** : 2026-01-30

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Architecture du Système](#architecture-du-système)
3. [Workflow Détaillé](#workflow-détaillé)
4. [Modèles & Technologies](#modèles--technologies)
5. [Pipeline de Génération](#pipeline-de-génération)
6. [Optimisations GPU](#optimisations-gpu)
7. [Paramètres de Configuration](#paramètres-de-configuration)
8. [Exemples d'Utilisation](#exemples-dutilisation)

---

## 🎯 Vue d'Ensemble

**Imagen** est un service de génération d'images basé sur **Stable Diffusion XL (SDXL)** avec support de prompts longs et transfert de style via IP-Adapter.

### Caractéristiques Principales

| Feature | Description | Status |
|---------|-------------|--------|
| 🚀 **Async Processing** | Génération non-bloquante via Celery | ✅ Production |
| 🧠 **Long Prompts** | Support >77 tokens via Compel | ✅ Production |
| 🎭 **Style Transfer** | IP-Adapter pour image de référence | ✅ Production |
| 💾 **GPU Optimized** | Fonctionne sur RTX 2080 Ti (11GB) | ✅ Production |
| 📊 **Job Tracking** | Status en temps réel | ✅ Production |
| 🔄 **Auto-Retry** | 3 tentatives sur OOM | ✅ Production |

### Spécifications Techniques

```
Résolution Native    : 1024x1024 pixels
Format de Sortie     : PNG (16-bit color)
Steps d'Inférence    : 30 (configurable)
Guidance Scale       : 7.5 (CFG)
Temps Moyen         : ~4-5 minutes par image
VRAM Requis         : ~10-11 GB
Queue Max           : 100 jobs simultanés
Timeout             : 10 minutes par génération
```

---

## 🏗️ Architecture du Système

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE GLOBALE                          │
└─────────────────────────────────────────────────────────────────────┘

          ┌─────────────┐
          │   CLIENT    │
          │  (HTTP/S)   │
          └──────┬──────┘
                 │
                 │ POST /generate
                 │ GET /status/{job_id}
                 │ GET /download/{filename}
                 ▼
    ┌────────────────────────────┐
    │     FastAPI Server         │
    │    (Port 8000/8009)        │
    │                            │
    │  • Validation Pydantic     │
    │  • Queue Management        │
    │  • StaticFiles Serving     │
    └──────────┬─────────────────┘
               │
               │ Celery Task
               ▼
    ┌────────────────────────────┐
    │     Redis Broker           │
    │    (Port 6379)             │
    │                            │
    │  • Task Queue              │
    │  • Result Backend          │
    │  • TTL: 1 hour             │
    └──────────┬─────────────────┘
               │
               │ Task Pickup
               ▼
    ┌────────────────────────────┐
    │   Celery Worker (GPU)      │
    │   Concurrency: 1 (solo)    │
    │                            │
    │  • NVIDIA CUDA Runtime     │
    │  • ElectraPipeline         │
    │  • Memory Management       │
    └──────────┬─────────────────┘
               │
               │ Pipeline Execution
               ▼
    ┌────────────────────────────┐
    │   SDXL Pipeline            │
    │   (GPU Accelerated)        │
    │                            │
    │  ┌──────────────────────┐  │
    │  │  1. Compel Encoding  │  │
    │  └──────────┬───────────┘  │
    │             ▼              │
    │  ┌──────────────────────┐  │
    │  │  2. IP-Adapter (opt) │  │
    │  └──────────┬───────────┘  │
    │             ▼              │
    │  ┌──────────────────────┐  │
    │  │  3. UNet Denoising   │  │
    │  └──────────┬───────────┘  │
    │             ▼              │
    │  ┌──────────────────────┐  │
    │  │  4. VAE Decoding     │  │
    │  └──────────┬───────────┘  │
    │             ▼              │
    │        PNG Image           │
    └────────────┬───────────────┘
                 │
                 │ Save to Disk
                 ▼
         ┌───────────────┐
         │ Docker Volume │
         │   /outputs/   │
         └───────────────┘
```

---

## 🔄 Workflow Détaillé

### Phase 1 : Réception de la Requête

```python
POST /generate
{
    "prompt": "a majestic dragon flying over mountains at sunset",
    "negative_prompt": "blurry, low quality, distorted, ugly",
    "ip_strength": 0.0
}
```

**Validations** :
- ✅ Schema Pydantic (`GenerationRequest`)
- ✅ Queue capacity check (<100 jobs)
- ✅ Redis connection health

**Réponse Immédiate** :
```json
{
    "job_id": "7f2b0887-3cdf-46ff-b83b-ff7685ac5b23",
    "status": "queued",
    "message": "Tâche en file d'attente. Position estimée: 3"
}
```

---

### Phase 2 : Task Queue & Distribution

```
Redis Queue
├─ Priority: FIFO (First In First Out)
├─ Serialization: JSON
├─ Retry Policy: 3 attempts, 10s backoff
└─ Timeout: 600s (10 minutes)

Celery Worker Pool
├─ Pool Type: solo (single-threaded)
├─ Concurrency: 1 task at a time
├─ Prefetch: 1 (no pre-loading)
└─ GPU: CUDA_VISIBLE_DEVICES=0
```

---

### Phase 3 : Pipeline de Génération

#### 3.1 - Initialisation (Singleton Pattern)

```python
ElectraPipeline Instance
├─ Lazy Loading (first use only)
├─ GPU Detection (cuda/cpu)
├─ Model Loading
│   ├─ SDXL Base (6.9 GB)
│   ├─ VAE Fix (335 MB)
│   └─ Text Encoders (2x)
└─ Compel Setup (dual encoders)
```

#### 3.2 - Prompt Processing avec Compel

**Pourquoi Compel ?**

CLIP (text encoder de base) limite les prompts à **77 tokens**. Compel permet de dépasser cette limite.

```
┌─────────────────────────────────────────────────────┐
│              COMPEL DUAL ENCODER SYSTEM             │
└─────────────────────────────────────────────────────┘

Input Prompt (unlimited length)
         │
         ├─────────────────┬─────────────────┐
         ▼                 ▼                 ▼
   Text Encoder 1    Text Encoder 2    Pooling
   (OpenCLIP         (OpenAI CLIP      (Global
    ViT-bigG)         ViT-L)            Features)
         │                 │                 │
         ▼                 ▼                 ▼
    Embeddings 1      Embeddings 2      Pooled Embeds
    (77x768)          (77x1280)         (1280)
         │                 │                 │
         └─────────────────┴─────────────────┘
                           │
                           ▼
                  Concatenated Embeddings
                  (Ready for UNet)
```

**Code** :
```python
# Tokenization + Embedding
conditioning, pooled = self.compel(prompt)
neg_conditioning, neg_pooled = self.compel(negative_prompt)
```

**Résultat** :
- ✅ Prompts de **548+ caractères** supportés
- ✅ Nuances sémantiques préservées
- ✅ Meilleure cohérence image/texte

#### 3.3 - IP-Adapter (Optionnel)

**Activé si** : `ip_strength > 0.0` et image de référence fournie

```
┌─────────────────────────────────────────────────────┐
│              IP-ADAPTER ARCHITECTURE                │
└─────────────────────────────────────────────────────┘

Reference Image (electra_ref.png)
         │
         ▼
  ┌──────────────┐
  │ CLIP Vision  │
  │  Encoder     │
  └──────┬───────┘
         │
         ▼
   Image Embeddings
   (1 x 1280)
         │
         ▼
  ┌──────────────┐
  │  Projection  │
  │  Network     │
  └──────┬───────┘
         │
         ▼
   Projected Features
         │
         ├─────────────────────┐
         │                     │
         ▼                     ▼
   Cross-Attention      +   Text Embeddings
   (in UNet layers)          (from Compel)
         │
         └─────────────────────┐
                               ▼
                        Fused Features
                        (Style + Prompt)
```

**Paramètres** :
- `ip_strength` : 0.0 (désactivé) → 1.0 (style complet)
- Recommandé : 0.5-0.7 pour équilibre prompt/style

**Code** :
```python
if reference_image_path and Path(reference_image_path).exists():
    ref_image = Image.open(reference_image_path).convert("RGB")
    self.pipe.load_ip_adapter(IP_ADAPTER_MODEL, ...)
    self.pipe.set_ip_adapter_scale(ip_strength)
    ip_args = {"ip_adapter_image": ref_image}
```

#### 3.4 - UNet Denoising (Cœur de SDXL)

```
┌─────────────────────────────────────────────────────┐
│           SDXL DENOISING PROCESS (30 STEPS)         │
└─────────────────────────────────────────────────────┘

Step 0: Pure Noise Latent (128x128x4)
   │
   │  ┌─────────────────────────────────────────┐
   │  │  UNet 2D Condition Model (2.6B params)  │
   │  │                                          │
   │  │  Input:                                  │
   │  │  ├─ Noisy latent (t=1000 → t=0)         │
   │  │  ├─ Text embeddings (conditioning)      │
   │  │  ├─ Timestep embedding                  │
   │  │  └─ IP features (if enabled)            │
   │  │                                          │
   │  │  Architecture:                           │
   │  │  ├─ Down blocks (3x)                    │
   │  │  ├─ Mid block (transformer)             │
   │  │  ├─ Up blocks (3x)                      │
   │  │  └─ Cross-attention layers              │
   │  │                                          │
   │  │  Output:                                 │
   │  │  └─ Noise prediction                    │
   │  └─────────────────┬───────────────────────┘
   │                    │
   │                    ▼
   │         Noise Removal (DDPM)
   │         Less noisy latent
   │                    │
   └────────────────────┘ (repeat 30 times)
              │
              ▼
   Clean Latent (128x128x4)
```

**Scheduler** : DPMSolver++ (default SDXL)
- Sampling steps : 30
- Guidance scale : 7.5 (CFG - Classifier-Free Guidance)

**Classifier-Free Guidance** :
```
predicted_noise = unconditional_noise + 7.5 * (conditional_noise - unconditional_noise)
```
→ Plus le CFG est élevé, plus l'image suit le prompt (mais moins de créativité)

**Code** :
```python
image = self.pipe(
    prompt_embeds=conditioning,
    pooled_prompt_embeds=pooled,
    negative_prompt_embeds=neg_conditioning,
    negative_pooled_prompt_embeds=neg_pooled,
    num_inference_steps=30,
    guidance_scale=7.5,
    height=1024,
    width=1024,
    **ip_args
).images[0]
```

#### 3.5 - VAE Decoding

```
┌─────────────────────────────────────────────────────┐
│              VAE DECODER (FP16 FIX)                 │
└─────────────────────────────────────────────────────┘

Latent Space (128x128x4)
         │
         ▼
  ┌──────────────┐
  │ VAE Decoder  │
  │ (madebyollin)│
  │              │
  │ Features:    │
  │ • FP16 opt   │
  │ • Slicing    │
  │ • Tiling     │
  └──────┬───────┘
         │
         ▼
  Pixel Space (1024x1024x3)
         │
         ▼
  ┌──────────────┐
  │ Clamp [0,1]  │
  │ → uint8      │
  └──────┬───────┘
         │
         ▼
   PNG Image (1-2 MB)
```

**Pourquoi le VAE Fix ?**

Le VAE standard SDXL peut produire des **artefacts noirs** en FP16. Le modèle `madebyollin/sdxl-vae-fp16-fix` corrige ce problème.

**Optimisations** :
- **VAE Slicing** : Traite l'image par batches de canaux
- **VAE Tiling** : Découpe l'image en tuiles 512x512

---

## 🧠 Modèles & Technologies

### Tableau Récapitulatif

| Modèle | Source | Taille | Rôle | Paramètres |
|--------|--------|--------|------|------------|
| **SDXL Base 1.0** | `stabilityai/stable-diffusion-xl-base-1.0` | 6.9 GB | UNet + Text Encoders | 2.6B (UNet) |
| **VAE FP16 Fix** | `madebyollin/sdxl-vae-fp16-fix` | 335 MB | Decoder latent→pixel | 83M |
| **IP-Adapter SDXL** | `h94/IP-Adapter` | 1.8 GB | Style transfer | 358M |
| **Compel** | `damian0815/compel` | Library | Long prompts | N/A |
| **PyTorch** | `pytorch.org` | N/A | ML Framework | N/A |
| **Diffusers** | `huggingface/diffusers` | N/A | Pipeline | N/A |

### Architecture des Text Encoders

```
┌───────────────────────────────────────────────────────┐
│            SDXL DUAL TEXT ENCODER SYSTEM              │
└───────────────────────────────────────────────────────┘

Text Encoder 1 (OpenCLIP ViT-bigG/14)
├─ Vocabulary: 49,408 tokens
├─ Hidden Size: 1,280
├─ Layers: 32
├─ Attention Heads: 20
├─ Parameters: 354M
└─ Output: [batch, 77, 1280]

Text Encoder 2 (OpenAI CLIP ViT-L/14)
├─ Vocabulary: 49,408 tokens
├─ Hidden Size: 768
├─ Layers: 12
├─ Attention Heads: 12
├─ Parameters: 123M
└─ Output: [batch, 77, 768]

Fusion Strategy
├─ Concatenation (channel-wise)
├─ Pooling (global features)
└─ Cross-attention in UNet
```

### UNet Architecture (SDXL)

```
┌───────────────────────────────────────────────────────┐
│              SDXL UNET 2D ARCHITECTURE                │
└───────────────────────────────────────────────────────┘

Input: [batch, 4, 128, 128]
   │
   ├─ Conv In (320 channels)
   │
   ├─ Down Block 1 (320 → 320)
   │   ├─ ResNet × 2
   │   ├─ Transformer × 2 (Cross-Attention)
   │   └─ Downsample
   │
   ├─ Down Block 2 (320 → 640)
   │   ├─ ResNet × 2
   │   ├─ Transformer × 2
   │   └─ Downsample
   │
   ├─ Down Block 3 (640 → 1280)
   │   ├─ ResNet × 2
   │   └─ Transformer × 10
   │
   ├─ Mid Block (1280)
   │   ├─ ResNet × 1
   │   ├─ Transformer × 10
   │   └─ ResNet × 1
   │
   ├─ Up Block 1 (1280 → 1280)
   │   ├─ ResNet × 3
   │   ├─ Transformer × 10
   │   └─ Upsample
   │
   ├─ Up Block 2 (1280 → 640)
   │   ├─ ResNet × 3
   │   ├─ Transformer × 2
   │   └─ Upsample
   │
   ├─ Up Block 3 (640 → 320)
   │   ├─ ResNet × 3
   │   └─ Transformer × 2
   │
   └─ Conv Out
       │
       ▼
Output: [batch, 4, 128, 128]

Total Parameters: ~2.6 Billion
```

---

## ⚡ Optimisations GPU

### Stratégie de Gestion Mémoire

```
┌───────────────────────────────────────────────────────┐
│         GPU MEMORY MANAGEMENT (11GB RTX 2080 Ti)     │
└───────────────────────────────────────────────────────┘

Technique 1: Model CPU Offload
┌─────────────────────────────────────────────────────┐
│ GPU VRAM (11 GB)              CPU RAM (64+ GB)      │
│                                                     │
│  Active Layer                 Idle Layers          │
│  ┌──────────┐                ┌──────────┐          │
│  │ UNet L12 │ ◄────swap─────►│ UNet L1  │          │
│  │ (500 MB) │                │ (500 MB) │          │
│  └──────────┘                └──────────┘          │
│                                                     │
│  Latent + Activations         Models Cache         │
│  (2-3 GB)                     (6 GB)               │
└─────────────────────────────────────────────────────┘

Technique 2: VAE Slicing
┌─────────────────────────────────────────────────────┐
│ Standard:                  Sliced:                  │
│                                                     │
│ ┌─────────────────┐        ┌─────┐ ┌─────┐         │
│ │  Full Image     │        │Slice│ │Slice│         │
│ │  1024x1024x3    │   →    │ 1   │→│  2  │→ ...   │
│ │  (10 GB VRAM)   │        │512x │ │512x │         │
│ └─────────────────┘        └─────┘ └─────┘         │
│                            (2 GB each)              │
└─────────────────────────────────────────────────────┘

Technique 3: VAE Tiling
┌─────────────────────────────────────────────────────┐
│  Image divisée en tuiles overlapping 512x512       │
│                                                     │
│  ┌──────┬──────┬──────┬──────┐                     │
│  │ T1   │ T2   │ T3   │ T4   │                     │
│  ├──────┼──────┼──────┼──────┤                     │
│  │ T5   │ T6   │ T7   │ T8   │   Processed         │
│  ├──────┼──────┼──────┼──────┤   sequentially      │
│  │ T9   │ T10  │ T11  │ T12  │   (1-2 GB each)     │
│  ├──────┼──────┼──────┼──────┤                     │
│  │ T13  │ T14  │ T15  │ T16  │                     │
│  └──────┴──────┴──────┴──────┘                     │
│                                                     │
│  Blend overlaps → seamless image                   │
└─────────────────────────────────────────────────────┘
```

### Configuration PyTorch

```python
# Environment Variables
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'

# Pipeline Optimizations
self.pipe.enable_model_cpu_offload()  # Dynamic layer swapping
self.pipe.enable_vae_slicing()        # Batch processing
self.pipe.enable_vae_tiling()         # Spatial tiling

# Memory Cleanup (after generation)
torch.cuda.empty_cache()
gc.collect()
```

### Profil VRAM Typique

```
┌───────────────────────────────────────────────────────┐
│            VRAM USAGE DURING GENERATION               │
└───────────────────────────────────────────────────────┘

Phase                        VRAM Used   Cumulative
─────────────────────────────────────────────────────────
Idle (models loaded)         6.5 GB      6.5 GB
Text Encoding (Compel)       +0.3 GB     6.8 GB
IP-Adapter (if enabled)      +0.5 GB     7.3 GB
UNet Forward Pass (peak)     +3.2 GB    10.5 GB
VAE Decoding (with tiling)   +0.4 GB    10.9 GB
─────────────────────────────────────────────────────────
Peak VRAM                               10.9 GB ✅

Safety Margin: 0.1 GB (11 GB total)
```

---

## ⚙️ Paramètres de Configuration

### Fichier : `app/config.py`

```python
# Modèles
SDXL_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
VAE_MODEL = "madebyollin/sdxl-vae-fp16-fix"
IP_ADAPTER_MODEL = "h94/IP-Adapter"
IP_ADAPTER_SUBFOLDER = "sdxl_models"
IP_ADAPTER_WEIGHT = "ip-adapter_sdxl.bin"

# Chemins
MODELS_DIR = Path("models")
OUTPUTS_DIR = Path("outputs")
REFERENCE_IMAGE = Path("reference/electra_ref.png")

# Paramètres de Génération
DEFAULT_STEPS = 30           # 20-50 recommandé
GUIDANCE_SCALE = 7.5         # 5.0-15.0 (↑ = plus fidèle au prompt)
IMAGE_SIZE = (1024, 1024)    # Native SDXL resolution

# Queue & Worker
REDIS_URL = "redis://localhost:6379/0"
MAX_QUEUE_SIZE = 100
CELERY_TASK_TIMEOUT = 600    # 10 minutes
CELERY_RESULT_EXPIRES = 3600 # 1 hour
```

### Tuning des Paramètres

| Paramètre | Effet si Augmenté | Recommandation |
|-----------|-------------------|----------------|
| **Steps** | + Qualité, + Temps | 30-40 (sweet spot) |
| **Guidance Scale** | + Adhérence prompt, - Créativité | 7.5 (défaut), 5-10 (créatif), 10-15 (précis) |
| **IP Strength** | + Style référence, - Prompt | 0.5-0.7 (équilibré) |
| **Resolution** | + Détails, ++ VRAM | 1024x1024 (optimal SDXL) |

---

## 📊 Exemples d'Utilisation

### Exemple 1 : Génération Simple

**Requête** :
```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a majestic dragon flying over snow-capped mountains at golden hour, cinematic lighting, highly detailed, 8k",
    "negative_prompt": "blurry, low quality, distorted, ugly, bad anatomy",
    "ip_strength": 0.0
  }'
```

**Réponse** :
```json
{
  "job_id": "abc123...",
  "status": "queued",
  "message": "Tâche en file d'attente. Position estimée: 1"
}
```

**Polling** :
```bash
# Vérifier le statut
curl http://localhost:8009/status/abc123...

# Réponse (en cours)
{
  "job_id": "abc123...",
  "status": "PROGRESS",
  "meta": {
    "current": 15,
    "total": 30,
    "percent": 50
  }
}

# Réponse (terminé)
{
  "job_id": "abc123...",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "filename": "20260130_123456_abc123.png",
    "path": "outputs/20260130_123456_abc123.png",
    "url": "/outputs/20260130_123456_abc123.png"
  }
}
```

**Téléchargement** :
```bash
curl http://localhost:8009/outputs/20260130_123456_abc123.png --output dragon.png
```

---

### Exemple 2 : Style Transfer avec IP-Adapter

**Setup** :
1. Placer image de référence : `reference/my_style.png`
2. Modifier `config.py` : `REFERENCE_IMAGE = Path("reference/my_style.png")`

**Requête** :
```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a futuristic cityscape at night, neon lights, cyberpunk aesthetic",
    "negative_prompt": "blurry, low quality",
    "ip_strength": 0.65
  }'
```

**Résultat** :
- Image générée avec le style de `my_style.png` (65%)
- Prompt textuel (35%)
- Fusion harmonieuse des deux influences

---

### Exemple 3 : Prompt Long (>77 tokens)

**Prompt** (548 caractères) :
```
"A breathtaking fantasy landscape featuring an ancient elven city built into
massive crystalline trees that glow with bioluminescent light, suspended
bridges of living wood connect towering structures, waterfalls cascade from
floating islands in the sky, mystical creatures soar between the branches,
volumetric god rays pierce through the canopy, magical runes shimmer on
stone archways, ethereal mist swirls around the base of the trees, distant
mountains frame the scene, golden hour lighting with purple and blue tones,
ultra detailed, trending on artstation, 8k, cinematic composition"
```

**Traitement** :
```
Original: 548 chars → ~110 tokens
CLIP Standard: Only first 77 tokens ❌
Compel: Full 110 tokens processed ✅

Résultat: Image respecte TOUS les détails du prompt
```

---

## 📈 Métriques de Performance

### Temps de Génération

| Configuration | Steps | Résolution | Temps Moyen | VRAM Peak |
|--------------|-------|------------|-------------|-----------|
| Rapide | 20 | 1024x1024 | ~2.5 min | 9.2 GB |
| Standard | 30 | 1024x1024 | ~4.3 min | 10.5 GB |
| Qualité | 50 | 1024x1024 | ~7.1 min | 10.8 GB |
| HD | 30 | 1536x1536 | ~9.2 min | OOM ❌ |

### Débit (Throughput)

```
Worker Configuration: 1 concurrent task (solo pool)

Throughput Théorique:
- 1 génération / 4.3 min
- ~14 images / heure
- ~336 images / jour (24/7)

Queue Management:
- Max 100 jobs en attente
- Position estimée affichée au client
- 503 Service Unavailable si queue pleine
```

---

## 🔍 Troubleshooting

### Erreurs Courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `CUDA out of memory` | VRAM insuffisante | Réduire steps ou activer optimisations |
| `Queue pleine (503)` | >100 jobs en attente | Attendre ou augmenter workers |
| `Timeout (10min)` | Génération trop complexe | Augmenter `CELERY_TASK_TIMEOUT` |
| `Artefacts noirs` | VAE non-fixé | Vérifier `VAE_MODEL` = fix version |
| `Prompt tronqué` | Compel désactivé | Vérifier init pipeline |

### Logs de Diagnostic

```bash
# Worker logs (génération)
docker-compose logs -f worker

# API logs (requêtes)
docker-compose logs -f api

# Redis logs (queue)
docker-compose logs -f redis

# Monitoring Celery
make flower  # http://localhost:5555
```

---

## 📚 Références

### Documentation Officielle

- [Stable Diffusion XL Paper](https://arxiv.org/abs/2307.01952)
- [Diffusers Library](https://huggingface.co/docs/diffusers)
- [Compel GitHub](https://github.com/damian0815/compel)
- [IP-Adapter Paper](https://arxiv.org/abs/2308.06721)

### Modèles HuggingFace

- [stabilityai/stable-diffusion-xl-base-1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- [madebyollin/sdxl-vae-fp16-fix](https://huggingface.co/madebyollin/sdxl-vae-fp16-fix)
- [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter)

### Technologies

- [FastAPI](https://fastapi.tiangolo.com/)
- [Celery](https://docs.celeryq.dev/)
- [PyTorch](https://pytorch.org/)
- [Redis](https://redis.io/)

---

## 📝 Changelog

### Version 1.0 (2026-01-30)
- ✅ Pipeline SDXL opérationnel
- ✅ Support Compel pour prompts longs
- ✅ IP-Adapter intégré
- ✅ Optimisations GPU (11GB)
- ✅ API REST complète
- ✅ Worker Celery async
- ✅ Documentation technique

---

**Imagen** | Made with ❤️ using SDXL
