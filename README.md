# 🎨 Imagen - AI Image Generation API

> Service de génération d'images basé sur Stable Diffusion XL avec support de prompts longs et style transfer

[![Production Ready](https://img.shields.io/badge/status-production%20ready-success)]()
[![SDXL](https://img.shields.io/badge/model-SDXL%201.0-blue)]()
[![GPU](https://img.shields.io/badge/GPU-RTX%202080%20Ti-green)]()
[![API](https://img.shields.io/badge/API-REST-orange)]()

---

## ✨ Fonctionnalités

- 🚀 **Génération Async** - Queue non-bloquante via Celery + Redis
- 🧠 **Prompts Longs** - Support illimité via Compel (>77 tokens)
- 🎭 **Style Transfer** - IP-Adapter pour images de référence
- 💾 **GPU Optimisé** - Fonctionne sur RTX 2080 Ti (11GB VRAM)
- 📊 **Job Tracking** - Suivi en temps réel de la génération
- 🔄 **Auto-Retry** - 3 tentatives automatiques sur erreur
- 🐳 **Docker Ready** - Déploiement conteneurisé avec NVIDIA runtime

---

## 🚀 Quick Start

### Prérequis

- Docker + Docker Compose
- NVIDIA GPU avec CUDA support
- 11+ GB VRAM

### Installation

```bash
# 1. Cloner le repo
git clone <repo-url>
cd imagen

# 2. Démarrer les services
docker-compose up -d

# 3. Vérifier le health check
curl http://localhost:8009/health
```

### Première Génération

```bash
# Créer une génération
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a beautiful sunset over mountains",
    "negative_prompt": "blurry, low quality"
  }' | jq -r '.job_id'

# Réponse: 7f2b0887-3cdf-46ff-b83b-ff7685ac5b23

# Télécharger l'image (après ~5 minutes)
curl http://localhost:8009/image/7f2b0887-3cdf-46ff-b83b-ff7685ac5b23 \
  -o sunset.png
```

---

## 📖 Documentation

### 📘 Pour les Utilisateurs

| Document | Description |
|----------|-------------|
| **[API.md](API.md)** | 📘 Référence API complète - Endpoints, schémas, exemples |
| **[API_UPDATES.md](API_UPDATES.md)** | 🚀 Nouvelles fonctionnalités et mises à jour |

### 🔧 Pour les Développeurs

| Document | Description |
|----------|-------------|
| **[WORKFLOW.md](WORKFLOW.md)** | 🔄 Architecture technique détaillée - Workflow, modèles, optimisations |
| **[PONY_XL_INTEGRATION.md](PONY_XL_INTEGRATION.md)** | 🦄 Guide d'implémentation PonyXL v6 + LoRA/LyCORIS |
| **[CLAUDE.md](CLAUDE.md)** | 📖 Documentation projet complète - Vue d'ensemble et référence |

---

## 🎯 Exemples d'Utilisation

### Python

```python
import requests
import time

API_URL = "http://localhost:8009"

# Créer une génération
response = requests.post(f"{API_URL}/generate", json={
    "prompt": "a majestic dragon flying over mountains",
    "negative_prompt": "blurry, low quality"
})
job_id = response.json()["job_id"]

# Polling jusqu'à succès
while True:
    response = requests.get(f"{API_URL}/image/{job_id}")
    if response.status_code == 200:
        with open("dragon.png", "wb") as f:
            f.write(response.content)
        print("✅ Image téléchargée!")
        break
    time.sleep(5)
```

### Bash

```bash
#!/bin/bash

# Fonction helper
generate_image() {
  local prompt="$1"
  local output="$2"

  # Créer job
  JOB_ID=$(curl -s -X POST http://localhost:8009/generate \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": \"$prompt\"}" \
    | jq -r '.job_id')

  echo "Job créé: $JOB_ID"

  # Polling automatique
  while ! curl -f -o "$output" http://localhost:8009/image/$JOB_ID 2>/dev/null; do
    echo "⏳ En cours..."
    sleep 5
  done

  echo "✅ Image sauvegardée: $output"
}

# Utilisation
generate_image "a cyberpunk city at night" "city.png"
```

---

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP
       ▼
┌──────────────┐       ┌─────────┐
│  FastAPI     │◄─────►│  Redis  │
│  (Port 8009) │       │ (Queue) │
└──────┬───────┘       └─────────┘
       │
       │ Celery Task
       ▼
┌──────────────┐       ┌──────────────┐
│ Celery Worker│──────►│ SDXL Pipeline│
│  (GPU Solo)  │       │   + Compel   │
└──────┬───────┘       │ + IP-Adapter │
       │               └──────────────┘
       ▼
┌──────────────┐
│ Docker Volume│
│  /outputs/   │
└──────────────┘
```

**Composants** :
- **FastAPI** : API REST (port 8009)
- **Redis** : Message broker & result backend
- **Celery Worker** : Exécution GPU (concurrency=1)
- **SDXL Pipeline** : Génération d'images (1024x1024)

---

## 🛠️ Commandes Utiles

### Makefile

```bash
make dev        # Lancer FastAPI avec reload
make worker     # Lancer Celery worker localement
make flower     # Dashboard monitoring Celery (port 5555)
make up         # Docker Compose startup
make down       # Docker Compose shutdown
make gpu        # Vérifier statut GPU (nvidia-smi)
```

### Docker Compose

```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Logs
docker-compose logs -f api
docker-compose logs -f worker

# Rebuild après changement de code
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 📊 Spécifications Techniques

### Modèles

| Modèle | Taille | Rôle |
|--------|--------|------|
| SDXL Base 1.0 | 6.9 GB | Génération principale |
| VAE FP16 Fix | 335 MB | Décodage sans artefacts |
| IP-Adapter SDXL | 1.8 GB | Transfert de style |

### Performance

| Métrique | Valeur |
|----------|--------|
| **Temps de génération** | ~4-5 minutes |
| **VRAM utilisée** | ~10-11 GB |
| **Résolution** | 1024x1024 pixels |
| **Format** | PNG (~1-2 MB) |
| **Throughput** | ~14 images/heure |

### Limites

| Limite | Valeur |
|--------|--------|
| **Queue max** | 100 jobs |
| **Timeout** | 10 minutes/génération |
| **Result TTL** | 1 heure |
| **Workers** | 1 (solo pool) |

---

## 🔧 Configuration

### Environnement

```bash
# Redis
REDIS_URL=redis://redis:6379/0

# GPU
CUDA_VISIBLE_DEVICES=0
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Celery
CELERY_WORKER_CONCURRENCY=1
```

### Paramètres de Génération

```python
# app/config.py

DEFAULT_STEPS = 30           # 20-50 recommandé
GUIDANCE_SCALE = 7.5         # 5.0-15.0 (CFG)
IMAGE_SIZE = (1024, 1024)    # Résolution native SDXL
MAX_QUEUE_SIZE = 100         # Limite de queue
```

---

## 🐛 Dépannage

### API ne répond pas

```bash
# Vérifier les conteneurs
docker-compose ps

# Vérifier les logs
docker-compose logs api --tail=50

# Redémarrer
docker-compose restart api
```

### Queue pleine (503)

```bash
# Vérifier le nombre de jobs en attente
docker-compose exec api python3 -c "
from app.worker import celery_app
inspector = celery_app.control.inspect()
print('Active:', inspector.active())
print('Scheduled:', inspector.scheduled())
"

# Attendre que la queue se vide
```

### Génération échouée (OOM)

```bash
# Vérifier les logs du worker
docker-compose logs worker --tail=100

# La tâche est automatiquement retentée 3 fois
```

### Images non visibles localement (DevContainer)

```bash
# Les images SONT dans le volume Docker
docker run --rm -v /workspaces/imagen/outputs:/outputs alpine ls -lh /outputs/

# Copier vers local
docker run --rm -v /workspaces/imagen/outputs:/src -v ${PWD}:/dest \
  alpine sh -c "cp /src/*.png /dest/"
```

---

## 🚧 Roadmap

### ✅ Version 1.0 (Actuelle)

- [x] SDXL Base 1.0
- [x] Support prompts longs (Compel)
- [x] IP-Adapter
- [x] API REST complète
- [x] Download direct par job ID

### 📋 Version 2.0 (Planifiée)

- [ ] PonyXL v6 support
- [ ] LoRA/LyCORIS dynamiques
- [ ] Multi-modèles configurables
- [ ] Seeds reproductibles
- [ ] Steps/CFG configurables par requête
- [ ] Endpoints `/models` et `/loras`

Voir [PONY_XL_INTEGRATION.md](PONY_XL_INTEGRATION.md) pour détails.

---

## 📄 Licence

Ce projet utilise des modèles open-source :

- **SDXL Base 1.0** : [CreativeML Open RAIL++-M License](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- **IP-Adapter** : [Apache 2.0](https://github.com/tencent-ailab/IP-Adapter)
- **Compel** : [MIT](https://github.com/damian0815/compel)

---

## 🙏 Remerciements

- [Stability AI](https://stability.ai/) - SDXL Base 1.0
- [Tencent AI Lab](https://github.com/tencent-ailab) - IP-Adapter
- [Damian Stewart](https://github.com/damian0815) - Compel
- [HuggingFace](https://huggingface.co/) - Diffusers Library
- [madebyollin](https://huggingface.co/madebyollin) - VAE FP16 Fix

---

## 📞 Support

### Documentation

- **API Reference** : [API.md](API.md)
- **Technical Workflow** : [WORKFLOW.md](WORKFLOW.md)
- **Project Overview** : [CLAUDE.md](CLAUDE.md)

### Monitoring

- **Celery Dashboard** : http://localhost:5555 (`make flower`)
- **API Health** : http://localhost:8009/health
- **Logs** : `docker-compose logs -f`

---

**Version** : 1.0
**Status** : Production Ready ✅
**Last Updated** : 2026-01-30
