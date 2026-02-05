# Imagen - Documentation Projet

> Documentation pour Claude Code - Vue d'ensemble complète du projet
> Dernière mise à jour : 2026-01-30

## 📸 Vue d'Ensemble

**Imagen** est un service d'API de génération d'images IA basé sur **Stable Diffusion XL (SDXL)**. Il permet de générer des images à partir de prompts textuels avec support du transfert de style via IP-Adapter.

**Optimisé pour** : GPU RTX 2080 Ti (11GB VRAM)

---

## 🏗️ Architecture

Architecture distribuée asynchrone avec 3 composants principaux :

### 1. API REST (api.py)
- **Framework** : FastAPI
- **Port** : 8009 (externe) → 8000 (interne)
- **Endpoints** :
  - `POST /generate` - Soumettre une génération d'image, retourne job_id
  - `GET /status/{job_id}` - Vérifier le statut (PENDING, PROGRESS, SUCCESS, FAILURE)
  - `GET /download/{filename}` - Télécharger l'image PNG générée
  - `GET /health` - Health check
- **Limite** : Max 100 jobs en attente

### 2. Worker Celery (worker.py)
- **Rôle** : Traitement GPU intensif des générations d'images
- **Configuration critique** :
  - Concurrence = 1 worker (essentiel pour mémoire GPU limitée)
  - Timeout = 10 minutes par tâche
  - Retry = 3 tentatives avec backoff 10s sur OOM
  - Prefetch = 1 (une tâche à la fois)
- **Fonctionnement** :
  1. Reçoit la requête (prompt, negative_prompt, ip_strength)
  2. Génère un ID unique (UUID + timestamp)
  3. Charge l'image de référence si disponible
  4. Génère l'image via pipeline SDXL
  5. Sauvegarde en PNG dans `/outputs/`
  6. Nettoie la mémoire GPU

### 3. Pipeline de Génération (pipeline.py)
- **Classe** : `ElectraPipeline` (Singleton, lazy-loading)
- **Optimisations mémoire** :
  - `enable_model_cpu_offload()` - Charge/décharge les couches à la demande
  - `enable_vae_slicing()` - Traite l'image en tranches
  - `enable_vae_tiling()` - Traitement en tuiles pour économiser VRAM
- **Features** :
  - Support prompts longs (via Compel avec dual text encoders)
  - IP-Adapter pour transfert de style depuis image de référence
  - Nettoyage automatique (garbage collection + CUDA cache clear)

---

## 🛠️ Stack Technique

| Composant | Technologie | Version | Usage |
|-----------|-------------|---------|-------|
| Web Framework | FastAPI | 0.105.0 | API REST |
| Task Queue | Celery | 5.3.4 | Distribution des tâches |
| Message Broker | Redis | 5.0.1 | Backend de queue |
| ML Framework | PyTorch | 2.1.2 | Deep learning |
| Image Generation | Diffusers | 0.25.0 | Pipeline SDXL |
| Transformers | Transformers | 4.36.0 | Text encoding |
| Prompt Enhancement | Compel | 2.0.2 | Support prompts longs |
| IP-Adapter | h94/IP-Adapter | - | Transfert de style |
| Image Processing | Pillow | 10.1.0 | I/O images |
| Server | Uvicorn | 0.24.0 | ASGI server |
| Container | Docker + CUDA | 12.1 | Déploiement GPU |

---

## 📁 Structure du Projet

```
imagen/
├── app/                          # Code principal
│   ├── api.py                   # FastAPI REST API
│   ├── worker.py                # Celery worker (tâches GPU)
│   ├── pipeline.py              # Pipeline SDXL
│   └── config.py                # Configuration & constantes
├── models/                       # Cache des modèles pré-entraînés
├── outputs/                      # Images générées
├── reference/                    # Images de référence pour IP-Adapter
│   └── leona.jpg               # Image de test (200KB)
├── docker-compose.yml           # Orchestration (Redis, API, Worker)
├── dockerfile                   # Image container CUDA
├── requirements.txt             # Dépendances Python
├── download_models.py           # Utilitaire téléchargement modèles
├── Makefile                     # Commandes développement
├── .pre-commit-config.yaml      # Hooks qualité (ruff, mypy)
└── CLAUDE.md                    # Ce fichier
```

---

## 🔄 Flux de Données

```
Requête Utilisateur
    ↓
FastAPI POST /generate
    ↓
Validation queue & création tâche
    ↓
Soumission Celery → Redis
    ↓
Worker Celery récupère la tâche
    ↓
Chargement pipeline SDXL (singleton, lazy-loaded)
    ↓
Encodage prompts avec Compel (dual text encoders)
    ↓
Chargement image référence + IP-Adapter (optionnel)
    ↓
Inférence SDXL (30 steps, CUDA GPU)
    ↓
Nettoyage mémoire (GC + CUDA cache)
    ↓
Sauvegarde PNG → outputs/
    ↓
Résultat → Redis
    ↓
Utilisateur poll GET /status/{job_id}
    ↓
Téléchargement GET /download/{filename}
```

---

## ⚙️ Configuration (config.py)

### Modèles
- **SDXL Base** : `stabilityai/stable-diffusion-xl-base-1.0`
- **VAE** : `madebyollin/sdxl-vae-fp16-fix` (correction artefacts noirs)
- **IP-Adapter** : `h94/IP-Adapter`

### Paramètres de Génération
- **Steps** : 30 (itérations d'inférence)
- **Guidance Scale** : 7.5 (adhérence au prompt)
- **Résolution** : 1024x1024 (native SDXL)

### Redis
- **URL** : `redis://localhost:6379/0`
- **Expiration résultats** : 1 heure

---

## 🚀 Commandes Makefile

```bash
make setup      # Installer dépendances + créer répertoires
make dev        # Lancer FastAPI avec reload
make worker     # Lancer worker Celery localement
make flower     # Dashboard monitoring Celery (port 5555)
make up         # Docker Compose startup production
make down       # Docker Compose shutdown
make clean      # Nettoyer cache files
make gpu        # Vérifier statut GPU (nvidia-smi)
make test       # Lancer pytest avec coverage
```

---

## 🐳 Docker Compose

### Services
1. **redis** : Message broker (port 6379)
2. **api** : FastAPI application (port 8009:8000)
3. **worker** : Celery worker (GPU-enabled)

Tous les services utilisent NVIDIA runtime pour accès GPU.

### Volumes Montés
- `./models:/app/models` - Cache modèles
- `./outputs:/app/outputs` - Images générées
- `./reference:/app/reference` - Images de référence

---

## 🎯 Features Clés

- ✅ **Traitement Asynchrone** - Génération non-bloquante via Celery
- ✅ **Optimisation GPU** - Efficient en VRAM (offloading, slicing, tiling)
- ✅ **Support Prompts Longs** - Via Compel (bypass limite 77 tokens)
- ✅ **Transfert de Style** - IP-Adapter pour génération basée sur image référence
- ✅ **Tracking Statut** - Mises à jour en temps réel
- ✅ **Gestion Queue** - Prévention surcharge serveur (max 100 jobs)
- ✅ **Tolérance aux Pannes** - Retry automatique sur OOM
- ✅ **Docker-Ready** - Containerisation complète avec support GPU NVIDIA
- ✅ **Outils Dev** - Pre-commit hooks, Makefile, type checking

---

## 🔧 Qualité du Code

### Pre-commit Hooks (.pre-commit-config.yaml)
- **Ruff** : Linter & formatter Python (auto-fix)
- **MyPy** : Type checking
- **Hooks standards** : Whitespace, file endings, YAML/JSON/TOML validation
- **Large file check** : Max 10MB (fichiers modèles)

### Tests
```bash
make test  # Pytest avec coverage
```

---

## 💾 Gestion Mémoire GPU

### Variables d'Environnement
```bash
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
```

### Stratégies
1. **CPU Offload** - Déchargement dynamique des couches
2. **VAE Slicing** - Traitement par tranches
3. **VAE Tiling** - Traitement par tuiles
4. **Garbage Collection** - Nettoyage après chaque génération
5. **CUDA Cache Clear** - Libération cache GPU
6. **Single Worker** - Une seule tâche à la fois

---

## 📝 Notes de Développement

### worker.py (Fichier Important)
C'est le cœur du traitement GPU. Il :
- Configure Celery avec Redis
- Définit `generate_image_task()` comme tâche Celery bound
- Gère la concurrence (CRITIQUE : 1 worker uniquement)
- Implémente retry logic et timeout
- Nettoie la mémoire GPU après chaque génération

### Debugging
```bash
# Vérifier GPU
make gpu

# Monitoring Celery
make flower  # http://localhost:5555

# Logs
docker-compose logs -f worker
docker-compose logs -f api
```

---

## 🎨 Exemple d'Utilisation

```bash
# 1. Démarrer les services
make up

# 2. Soumettre une génération
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a beautiful sunset over mountains",
    "negative_prompt": "blurry, low quality",
    "ip_strength": 0.0
  }'
# Réponse: {"job_id": "abc-123"}

# 3. Vérifier le statut
curl http://localhost:8009/status/abc-123
# Réponse: {"state": "SUCCESS", "result": {...}}

# 4. Télécharger l'image
curl http://localhost:8009/download/20260130_123456_abc123.png --output image.png
```

---

## 🚨 Points d'Attention

1. **Concurrence Worker = 1** : Ne JAMAIS augmenter (OOM GPU garanti)
2. **Queue Max = 100** : Protection contre surcharge
3. **Timeout = 10min** : Générations complexes peuvent être longues
4. **VAE Fix** : Utilisation obligatoire du VAE fix pour éviter artefacts
5. **Compel** : Nécessaire pour prompts > 77 tokens

---

## 📚 Documentation du Projet

### Guides Utilisateur

- **[API.md](API.md)** - 📘 Référence API complète (endpoints, schémas, exemples)
- **[WORKFLOW.md](WORKFLOW.md)** - 🔄 Architecture technique détaillée (workflow, modèles, optimisations)
- **[API_UPDATES.md](API_UPDATES.md)** - 🚀 Nouvelles fonctionnalités et mises à jour

### Guides Développeur

- **[PONY_XL_INTEGRATION.md](PONY_XL_INTEGRATION.md)** - 🦄 Guide d'implémentation PonyXL v6 + LoRA/LyCORIS
- **[CLAUDE.md](CLAUDE.md)** - 📖 Ce fichier - Documentation projet complète

## 🔗 Références Externes

- [Stable Diffusion XL](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- [IP-Adapter](https://github.com/tencent-ailab/IP-Adapter)
- [Compel](https://github.com/damian0815/compel)
- [Diffusers](https://huggingface.co/docs/diffusers)

---

**État du Projet** : Production-ready ✅

---

## ⚠️ DevContainer - Accès aux Images Générées

### Problème Technique

Dans un DevContainer avec Docker-from-Docker sur WSL2, le répertoire `./outputs` local est DIFFÉRENT du volume Docker `/workspaces/imagen/outputs` utilisé par les conteneurs. C'est dû à l'isolation des namespaces.

**Les images SONT correctement sauvegardées** dans le volume Docker partagé entre API et Worker, mais invisibles depuis le DevContainer local.

### Solutions

#### 1. Accès via Docker (Recommandé)
```bash
# Lister les images
docker run --rm -v /workspaces/imagen/outputs:/outputs alpine ls -lh /outputs/

# Copier UNE image vers local
docker run --rm -v /workspaces/imagen/outputs:/outputs alpine cat /outputs/IMAGE.png > ./IMAGE.png

# Copier TOUTES les images
docker run --rm -v /workspaces/imagen/outputs:/src -v ${PWD}:/dest alpine sh -c "cp /src/*.png /dest/"
```

#### 2. Accès via API (Cas d'usage normal)
Les images sont accessibles via l'API sur `/outputs/<filename>` grâce au `StaticFiles` mount.

```bash
# Dans un navigateur ou depuis l'hôte
curl http://localhost:8009/outputs/20260130_043240_aaad6da8.png --output image.png
```

#### 3. Utiliser le script helper
```bash
./show-outputs.sh list   # Liste les images
./show-outputs.sh sync   # Copie toutes vers outputs_local/
```

### Vérification que le Système Fonctionne

```bash
# Les conteneurs voient bien les images :
docker run --rm -v /workspaces/imagen/outputs:/test alpine ls -lh /test/
# ✅ Doit afficher toutes les images

# Le DevContainer NE voit PAS les images (c'est normal) :
ls /workspaces/imagen/outputs/
# Peut être vide ou obsolète
```

**Conclusion** : Le système fonctionne parfaitement. C'est juste l'accès depuis le DevContainer qui nécessite docker run.
