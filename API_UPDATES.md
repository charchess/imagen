# 🚀 Imagen - Mises à Jour API

> Nouvelles fonctionnalités : PonyXL v6, LoRA/LyCORIS, Download par Job ID

---

## 📋 Résumé des Changements

### 1. ✅ Persistence des Modèles (Déjà Actif)

Les modèles sont **déjà persistés** via volume Docker :
```yaml
volumes:
  - ${PWD}/models:/app/models  # 11 GB de cache persisté
```

**Modèles actuellement en cache** :
- SDXL Base 1.0 (6.9 GB)
- VAE FP16 Fix (335 MB)
- IP-Adapter SDXL (1.8 GB)

---

### 2. 🦄 Support Multi-Modèles + LoRA/LyCORIS

**Architecture** : Voir [PONY_XL_INTEGRATION.md](PONY_XL_INTEGRATION.md)

**Nouveaux paramètres API** :
```json
{
  "model": "pony-xl-v6",           // Nouveau: sélection du modèle
  "loras": [                        // Nouveau: stack de LoRAs
    {"name": "style-anime", "weight": 0.75},
    {"name": "character-detailed", "weight": 0.8}
  ],
  "steps": 35,                      // Nouveau: configurable
  "guidance_scale": 8.0,            // Nouveau: configurable
  "seed": 42                        // Nouveau: reproductibilité
}
```

---

### 3. 📥 Download Direct par Job ID

**Nouveau Endpoint** : `GET /image/{job_id}`

Retourne directement l'image PNG sans avoir besoin du filename.

---

## 🔗 Nouveaux Endpoints API

### 1. Liste des Modèles Disponibles

```bash
GET /models
```

**Réponse** :
```json
{
  "models": [
    {
      "id": "sdxl-base",
      "name": "SDXL Base 1.0",
      "supported_loras": []
    },
    {
      "id": "pony-xl-v6",
      "name": "PonyXL v6",
      "supported_loras": ["style-anime", "character-detailed"]
    }
  ]
}
```

---

### 2. Liste des LoRAs Disponibles

```bash
GET /loras
```

**Réponse** :
```json
{
  "loras": [
    {
      "id": "style-anime",
      "name": "Anime Style LoRA",
      "default_weight": 0.75,
      "trigger_words": ["anime style", "detailed"]
    },
    {
      "id": "character-detailed",
      "name": "Character Detail Enhancement",
      "default_weight": 0.6,
      "trigger_words": null
    }
  ]
}
```

---

### 3. Téléchargement Direct par Job ID ✨ NOUVEAU

```bash
GET /image/{job_id}
```

**Comportement** :
- ✅ **200 OK** : Retourne l'image PNG
- ⏳ **202 Accepted** : Génération en cours
- ❌ **404 Not Found** : Job ID inexistant
- ❌ **500 Internal Error** : Échec de génération

**Exemple** :
```bash
# 1. Créer une génération
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a beautiful sunset", "model": "sdxl-base"}' \
  | jq -r '.job_id'

# Réponse: 7f2b0887-3cdf-46ff-b83b-ff7685ac5b23

# 2. Récupérer l'image directement (polling)
curl http://localhost:8009/image/7f2b0887-3cdf-46ff-b83b-ff7685ac5b23 \
  --output sunset.png

# Si en cours (202):
# {"status":"processing","message":"Image en cours de génération","state":"PROGRESS"}

# Si terminé (200):
# [BINARY PNG DATA] → sunset.png
```

**Headers de Réponse** :
```
Content-Type: image/png
X-Job-ID: 7f2b0887-3cdf-46ff-b83b-ff7685ac5b23
X-Generation-Metadata: {"model": "sdxl-base", "steps": 30, ...}
```

---

## 📖 Exemples d'Utilisation

### Workflow Simple (1 requête)

**Avant** (2 appels API) :
```bash
# 1. Créer job
JOB_ID=$(curl -X POST .../generate -d '...' | jq -r '.job_id')

# 2. Attendre + récupérer filename
FILENAME=$(curl .../status/$JOB_ID | jq -r '.result.filename')

# 3. Télécharger
curl .../download/$FILENAME -o image.png
```

**Maintenant** (1 appel en boucle) :
```bash
# 1. Créer job
JOB_ID=$(curl -X POST .../generate -d '...' | jq -r '.job_id')

# 2. Télécharger direct (retry jusqu'à 200 OK)
while ! curl -f .../image/$JOB_ID -o image.png; do sleep 5; done
```

---

### Script Python avec Polling

```python
import requests
import time
from pathlib import Path

API_URL = "http://localhost:8009"

def generate_and_download(prompt: str, output_file: str, **kwargs):
    """Génère une image et la télécharge automatiquement"""

    # 1. Créer la génération
    response = requests.post(f"{API_URL}/generate", json={
        "prompt": prompt,
        **kwargs
    })
    job_id = response.json()["job_id"]
    print(f"✅ Job créé: {job_id}")

    # 2. Polling sur /image/{job_id}
    while True:
        response = requests.get(f"{API_URL}/image/{job_id}")

        if response.status_code == 200:
            # Image prête !
            Path(output_file).write_bytes(response.content)
            print(f"✅ Image téléchargée: {output_file}")

            # Métadonnées dans les headers
            metadata = response.headers.get("X-Generation-Metadata")
            print(f"📊 Metadata: {metadata}")
            return output_file

        elif response.status_code == 202:
            # En cours
            data = response.json()
            print(f"⏳ {data['message']} ({data['state']})")
            time.sleep(5)

        elif response.status_code == 500:
            # Échec
            error = response.json()
            print(f"❌ Erreur: {error}")
            raise Exception(error)

        else:
            print(f"❌ Erreur inattendue: {response.status_code}")
            raise Exception(response.text)


# Utilisation
generate_and_download(
    prompt="a majestic dragon flying over mountains",
    output_file="dragon.png",
    model="sdxl-base",
    steps=30
)
```

---

### Génération avec PonyXL + LoRAs

```python
generate_and_download(
    prompt="cute anime girl with long pink hair, detailed eyes, fantasy background",
    output_file="anime_girl.png",
    model="pony-xl-v6",
    loras=[
        {"name": "style-anime", "weight": 0.75},
        {"name": "character-detailed", "weight": 0.8}
    ],
    steps=35,
    guidance_scale=8.0,
    seed=42  # Reproductible
)
```

---

### Batch Generation avec Seeds

```python
# Générer 5 variations du même prompt avec seeds différents
base_prompt = "a futuristic cityscape at night, neon lights"

for i in range(5):
    generate_and_download(
        prompt=base_prompt,
        output_file=f"city_variation_{i}.png",
        model="pony-xl-v6",
        seed=1000 + i,  # Seeds consécutifs
        steps=30
    )
```

---

## 🔄 Workflow Comparatif

### Ancien Workflow (status + download)

```
┌─────────────────────┐
│  POST /generate     │
│  → {job_id}         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  GET /status/{id}   │◄─── Polling (toutes les 5s)
│  → {state, result}  │
└──────────┬──────────┘
           │
           │ (wait for SUCCESS)
           ▼
┌─────────────────────┐
│ Extract filename    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ GET /download/{fn}  │
│ → PNG binary        │
└─────────────────────┘

Total: 3 étapes
```

### Nouveau Workflow (image direct)

```
┌─────────────────────┐
│  POST /generate     │
│  → {job_id}         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  GET /image/{id}    │◄─── Polling (toutes les 5s)
│                     │
│  202: En cours      │
│  200: PNG binary    │
└─────────────────────┘

Total: 2 étapes ✅
```

---

## 📊 Tableau Récapitulatif des Endpoints

| Endpoint | Méthode | Description | Nouveau |
|----------|---------|-------------|---------|
| `/generate` | POST | Créer génération | ✅ Étendu |
| `/status/{job_id}` | GET | Vérifier statut job | Existant |
| `/download/{filename}` | GET | Télécharger par nom | Existant |
| `/image/{job_id}` | GET | **Télécharger par job ID** | ✨ **NOUVEAU** |
| `/models` | GET | **Liste modèles disponibles** | ✨ **NOUVEAU** |
| `/loras` | GET | **Liste LoRAs disponibles** | ✨ **NOUVEAU** |
| `/health` | GET | Health check | Existant |

---

## 🧪 Tests

### Test 1 : Download par Job ID

```bash
# Créer job
JOB_ID=$(curl -s -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test image", "model": "sdxl-base"}' \
  | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# Attendre 30s
sleep 30

# Tenter download (devrait être en cours = 202)
curl -v http://localhost:8009/image/$JOB_ID

# Attendre 4 minutes
sleep 240

# Download final (devrait être 200 OK)
curl http://localhost:8009/image/$JOB_ID -o test.png
file test.png  # Devrait afficher: PNG image data, 1024 x 1024
```

### Test 2 : Job ID Invalide

```bash
curl -v http://localhost:8009/image/invalid-job-id
# Devrait retourner 404 Not Found
```

### Test 3 : PonyXL + LoRA (après implémentation)

```bash
JOB_ID=$(curl -s -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "cute anime character",
    "model": "pony-xl-v6",
    "loras": [{"name": "style-anime", "weight": 0.75}],
    "steps": 30,
    "seed": 42
  }' | jq -r '.job_id')

# Attendre et télécharger
while ! curl -f -o pony_test.png http://localhost:8009/image/$JOB_ID; do
  echo "En cours..."
  sleep 5
done

echo "✅ Téléchargé: pony_test.png"
```

---

## 🚀 Migration & Déploiement

### Phase 1 : Image Direct Download (Immédiat) ✅ FAIT

```bash
# 1. Code déjà ajouté dans api.py
# 2. Redémarrer API
docker-compose restart api

# 3. Tester
curl http://localhost:8009/image/{job_id}
```

### Phase 2 : PonyXL + LoRA (À Implémenter)

**Fichiers à créer** :
- ✅ `app/models_config.py` - Configuration modèles/LoRAs
- ✅ Refactoriser `app/pipeline.py` → `FlexiblePipeline`
- ✅ Mettre à jour `app/worker.py` - Nouveaux paramètres
- ✅ Mettre à jour `app/api.py` - Endpoints `/models` et `/loras`

**Commandes** :
```bash
# 1. Installer dépendances
pip install peft>=0.7.0 lycoris-lora>=1.0.0

# 2. Télécharger PonyXL v6
python download_models.py --model pony-xl-v6

# 3. Rebuild containers
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 📝 Documentation Développeur

### Endpoint `/image/{job_id}` - Spécifications

**URL** : `GET /image/{job_id}`

**Paramètres** :
- `job_id` (path, required) : UUID de la tâche Celery

**Codes de Réponse** :

| Code | Status | Signification | Action Client |
|------|--------|---------------|---------------|
| 200 | OK | Image prête | Sauvegarder PNG |
| 202 | Accepted | En cours | Retry après 5s |
| 404 | Not Found | Job inexistant | Vérifier job_id |
| 500 | Error | Échec génération | Vérifier logs |

**Headers de Réponse (200 OK)** :
```
Content-Type: image/png
Content-Length: 1575000
X-Job-ID: 7f2b0887-3cdf-46ff-b83b-ff7685ac5b23
X-Generation-Metadata: {"model": "sdxl-base", "steps": 30, "seed": null}
```

**Body de Réponse (202 Accepted)** :
```json
{
  "status": "processing",
  "message": "Image en cours de génération",
  "state": "PROGRESS",
  "meta": {
    "current": 15,
    "total": 30,
    "percent": 50
  }
}
```

**Body de Réponse (500 Error)** :
```json
{
  "status": "failed",
  "error": "CUDA out of memory"
}
```

---

## 🎯 Avantages des Changements

### ✅ Download par Job ID

| Avant | Après |
|-------|-------|
| 3 appels API (generate → status → download) | 2 appels (generate → image polling) |
| Client doit parser JSON | Client récupère PNG direct |
| 2 variables à tracker (job_id + filename) | 1 variable (job_id) |
| Code complexe | Code simple |

### ✅ Multi-Modèles + LoRA

| Avant | Après |
|-------|-------|
| 1 modèle fixe (SDXL Base) | N modèles configurables |
| Pas de customisation style | Stack de LoRAs (jusqu'à 4) |
| Pas de reproductibilité | Seeds fixes |
| Steps/CFG fixes | Configurables par requête |

---

## 📚 Références

- [WORKFLOW.md](WORKFLOW.md) - Architecture détaillée du système
- [PONY_XL_INTEGRATION.md](PONY_XL_INTEGRATION.md) - Guide d'implémentation PonyXL
- [CLAUDE.md](CLAUDE.md) - Documentation projet complète

---

**Dernière mise à jour** : 2026-01-30
**Status** : Image Direct Download ✅ | PonyXL + LoRA 📋 En planification
