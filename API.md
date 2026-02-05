# 📘 Imagen API Reference

> API REST pour la génération d'images via Stable Diffusion XL

**Base URL** : `http://localhost:8009`
**Version** : 2.0
**Format** : JSON
**Authentication** : None (pour le moment)

---

## 📋 Table des Matières

- [Endpoints](#endpoints)
  - [POST /generate](#post-generate)
  - [GET /status/{job_id}](#get-statusjob_id)
  - [GET /image/{job_id}](#get-imagejob_id)
  - [GET /download/{filename}](#get-downloadfilename)
  - [GET /models](#get-models) ✨ NEW
  - [GET /loras](#get-loras) ✨ NEW
  - [GET /health](#get-health)
- [Schémas de Données](#schémas-de-données)
- [Codes d'Erreur](#codes-derreur)
- [Exemples Pratiques](#exemples-pratiques)
- [Limites & Quotas](#limites--quotas)

---

## Endpoints

### POST /generate

Crée une nouvelle tâche de génération d'image.

**URL** : `/generate`
**Méthode** : `POST`
**Content-Type** : `application/json`

#### Requête

```json
{
  "prompt": "a beautiful sunset over mountains",
  "negative_prompt": "blurry, low quality, distorted",
  "model": "sdxl-base",
  "loras": [
    {
      "name": "anime-style",
      "weight": 0.75
    }
  ],
  "steps": 30,
  "guidance_scale": 7.5,
  "seed": 42,
  "ip_strength": 0.0
}
```

##### Paramètres

| Champ | Type | Requis | Défaut | Description |
|-------|------|--------|--------|-------------|
| `prompt` | string | ✅ Oui | - | Description de l'image à générer |
| `negative_prompt` | string | ❌ Non | Défaut du modèle | Éléments à éviter dans l'image |
| `model` | string | ❌ Non | `"sdxl-base"` | ID du modèle base (voir `/models`) |
| `loras` | array | ❌ Non | `[]` | Liste des LoRAs à appliquer (voir `/loras`) |
| `steps` | integer | ❌ Non | `30` | Nombre d'étapes de diffusion (10-100) |
| `guidance_scale` | float | ❌ Non | `7.5` | CFG scale pour le respect du prompt (1.0-30.0) |
| `seed` | integer | ❌ Non | `null` | Seed pour reproductibilité (null = aléatoire) |
| `ip_strength` | float | ❌ Non | `0.0` | Force du style transfer (0.0-1.0) |

**Note** : Les trigger words des LoRAs sont automatiquement ajoutés au prompt si absents.

#### Réponse Succès (201 Created)

```json
{
  "job_id": "7f2b0887-3cdf-46ff-b83b-ff7685ac5b23",
  "status": "queued",
  "message": "Tâche en file d'attente. Position estimée: 3"
}
```

##### Champs de Réponse

| Champ | Type | Description |
|-------|------|-------------|
| `job_id` | string (UUID) | Identifiant unique de la tâche |
| `status` | string | État initial (`queued`) |
| `message` | string | Message informatif |

#### Réponse Erreur (503 Service Unavailable)

```json
{
  "detail": "Queue pleine, réessayez plus tard"
}
```

**Conditions** : Plus de 100 jobs en attente

#### Exemple

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a majestic dragon flying over mountains at sunset",
    "negative_prompt": "blurry, low quality",
    "ip_strength": 0.0
  }'
```

---

### GET /status/{job_id}

Récupère le statut d'une tâche de génération.

**URL** : `/status/{job_id}`
**Méthode** : `GET`

#### Paramètres URL

| Paramètre | Type | Description |
|-----------|------|-------------|
| `job_id` | string (UUID) | Identifiant de la tâche |

#### Réponse - En Attente (PENDING)

```json
{
  "job_id": "7f2b0887-3cdf-46ff-b83b-ff7685ac5b23",
  "status": "PENDING",
  "result": null
}
```

#### Réponse - En Cours (PROGRESS)

```json
{
  "job_id": "7f2b0887-3cdf-46ff-b83b-ff7685ac5b23",
  "status": "PROGRESS",
  "result": null,
  "meta": {
    "step": "generation_gpu",
    "progress": 45
  }
}
```

#### Réponse - Succès (SUCCESS)

```json
{
  "job_id": "7f2b0887-3cdf-46ff-b83b-ff7685ac5b23",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "filename": "sdxl_base_20260130_123456_abc123.png",
    "path": "outputs/sdxl_base_20260130_123456_abc123.png",
    "url": "/outputs/sdxl_base_20260130_123456_abc123.png",
    "metadata": {
      "model": "sdxl-base",
      "loras": [],
      "steps": 30,
      "guidance_scale": 7.5,
      "seed": 42,
      "ip_strength": 0.0
    }
  }
}
```

##### Champs de Réponse (SUCCESS)

| Champ | Type | Description |
|-------|------|-------------|
| `result.status` | string | `"success"` |
| `result.filename` | string | Nom du fichier PNG généré (préfixé par le modèle) |
| `result.path` | string | Chemin relatif du fichier |
| `result.url` | string | URL de téléchargement |
| `result.metadata` | object | Métadonnées de génération (modèle, LoRAs, paramètres) |

#### Réponse - Échec (FAILURE)

```json
{
  "job_id": "7f2b0887-3cdf-46ff-b83b-ff7685ac5b23",
  "status": "FAILURE",
  "result": null,
  "error": "CUDA out of memory"
}
```

#### Exemple

```bash
curl http://localhost:8009/status/7f2b0887-3cdf-46ff-b83b-ff7685ac5b23
```

---

### GET /image/{job_id}

Télécharge directement l'image PNG par job ID (endpoint simplifié).

**URL** : `/image/{job_id}`
**Méthode** : `GET`

#### Paramètres URL

| Paramètre | Type | Description |
|-----------|------|-------------|
| `job_id` | string (UUID) | Identifiant de la tâche |

#### Réponse - Succès (200 OK)

**Content-Type** : `image/png`
**Body** : Données binaires PNG

**Headers** :
```
Content-Type: image/png
Content-Length: 1575000
X-Job-ID: 7f2b0887-3cdf-46ff-b83b-ff7685ac5b23
X-Generation-Metadata: {"model": "sdxl-base", "steps": 30, ...}
```

#### Réponse - En Cours (202 Accepted)

```json
{
  "detail": {
    "status": "processing",
    "message": "Image en cours de génération",
    "state": "PROGRESS",
    "meta": {
      "step": "generation_gpu",
      "progress": 65
    }
  }
}
```

**Recommandation** : Réessayer après 5-10 secondes

#### Réponse - Job Non Trouvé (404 Not Found)

```json
{
  "detail": "Job ID non trouvé"
}
```

#### Réponse - Échec de Génération (500 Internal Server Error)

```json
{
  "detail": {
    "status": "failed",
    "error": "CUDA out of memory"
  }
}
```

#### Exemple - Polling Automatique

```bash
#!/bin/bash
JOB_ID="7f2b0887-3cdf-46ff-b83b-ff7685ac5b23"

# Polling jusqu'à succès
while true; do
  HTTP_CODE=$(curl -s -o image.png -w "%{http_code}" \
    http://localhost:8009/image/$JOB_ID)

  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Image téléchargée: image.png"
    break
  elif [ "$HTTP_CODE" = "202" ]; then
    echo "⏳ Génération en cours..."
    sleep 5
  else
    echo "❌ Erreur HTTP $HTTP_CODE"
    break
  fi
done
```

---

### GET /download/{filename}

Télécharge une image par son nom de fichier.

**URL** : `/download/{filename}`
**Méthode** : `GET`

#### Paramètres URL

| Paramètre | Type | Description |
|-----------|------|-------------|
| `filename` | string | Nom du fichier PNG (ex: `20260130_123456_abc123.png`) |

#### Réponse - Succès (200 OK)

**Content-Type** : `image/png`
**Body** : Données binaires PNG

#### Réponse - Fichier Non Trouvé (404 Not Found)

```json
{
  "detail": "Image non trouvée"
}
```

#### Exemple

```bash
curl http://localhost:8009/download/20260130_123456_abc123.png \
  --output my_image.png
```

---

### GET /models

Liste les modèles base disponibles.

**URL** : `/models`
**Méthode** : `GET`

#### Réponse (200 OK)

```json
{
  "models": [
    {
      "id": "sdxl-base",
      "name": "SDXL Base 1.0",
      "description": "Stable Diffusion XL base model - polyvalent",
      "vae_path": "madebyollin/sdxl-vae-fp16-fix",
      "default_negative": "low quality, blurry, distorted, ugly, bad anatomy"
    }
  ]
}
```

##### Champs de Réponse

| Champ | Type | Description |
|-------|------|-------------|
| `models` | array | Liste des modèles disponibles |
| `models[].id` | string | Identifiant unique du modèle (à utiliser dans `/generate`) |
| `models[].name` | string | Nom complet du modèle |
| `models[].description` | string | Description du modèle |
| `models[].vae_path` | string | VAE custom utilisé (optionnel) |
| `models[].default_negative` | string | Negative prompt par défaut du modèle |

#### Exemple

```bash
curl http://localhost:8009/models | jq '.'
```

---

### GET /loras

Liste les LoRAs et LyCORIS disponibles.

**URL** : `/loras`
**Méthode** : `GET`

#### Réponse (200 OK)

```json
{
  "loras": [
    {
      "id": "anime-style",
      "name": "Anime Style Enhancer",
      "description": "Améliore le style anime et les détails",
      "default_weight": 0.75,
      "trigger_words": ["anime style", "detailed"]
    },
    {
      "id": "character-detail",
      "name": "Character Detail Enhancement",
      "description": "Améliore les détails des personnages (visage, yeux, etc.)",
      "default_weight": 0.6,
      "trigger_words": null
    }
  ]
}
```

##### Champs de Réponse

| Champ | Type | Description |
|-------|------|-------------|
| `loras` | array | Liste des LoRAs disponibles |
| `loras[].id` | string | Identifiant unique du LoRA (à utiliser dans `/generate`) |
| `loras[].name` | string | Nom complet du LoRA |
| `loras[].description` | string | Description du LoRA |
| `loras[].default_weight` | float | Poids recommandé (0.0-2.0) |
| `loras[].trigger_words` | array\|null | Mots-clés à inclure dans le prompt (auto-ajoutés) |

#### Exemple

```bash
curl http://localhost:8009/loras | jq '.'
```

---

### GET /health

Health check de l'API.

**URL** : `/health`
**Méthode** : `GET`

#### Réponse (200 OK)

```json
{
  "status": "ok",
  "gpu_available": true,
  "queue_broker": "connected"
}
```

##### Champs de Réponse

| Champ | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` si l'API fonctionne |
| `gpu_available` | boolean | État du GPU |
| `queue_broker` | string | État de Redis |

#### Exemple

```bash
curl http://localhost:8009/health
```

---

## Schémas de Données

### GenerationRequest

```typescript
{
  prompt: string;                  // Requis
  negative_prompt?: string;        // Optionnel, défaut: par modèle
  model?: string;                  // Optionnel, défaut: "sdxl-base"
  loras?: LoRARequest[];           // Optionnel, défaut: []
  steps?: number;                  // Optionnel, défaut: 30, plage: 10-100
  guidance_scale?: number;         // Optionnel, défaut: 7.5, plage: 1.0-30.0
  seed?: number | null;            // Optionnel, défaut: null (aléatoire)
  ip_strength?: number;            // Optionnel, défaut: 0.0, plage: 0.0-1.0
}
```

### LoRARequest

```typescript
{
  name: string;     // ID du LoRA (voir /loras)
  weight: number;   // Poids du LoRA, défaut: 0.8, plage: 0.0-2.0
}
```

### GenerationResponse

```typescript
{
  job_id: string;     // UUID v4
  status: string;     // "queued"
  message: string;    // Message informatif
}
```

### JobStatus

```typescript
{
  job_id: string;           // UUID v4
  status: JobState;         // Voir JobState ci-dessous
  result?: JobResult;       // Présent si SUCCESS
  error?: string;           // Présent si FAILURE
  meta?: ProgressMeta;      // Présent si PROGRESS
}
```

#### JobState (enum)

| Valeur | Description |
|--------|-------------|
| `PENDING` | Tâche en attente dans la queue |
| `STARTED` | Tâche démarrée |
| `PROGRESS` | Génération en cours |
| `SUCCESS` | Génération réussie |
| `FAILURE` | Génération échouée |

#### JobResult

```typescript
{
  status: "success";
  filename: string;        // Ex: "sdxl_base_20260130_123456_abc123.png"
  path: string;           // Ex: "outputs/sdxl_base_20260130_123456_abc123.png"
  url: string;            // Ex: "/outputs/sdxl_base_20260130_123456_abc123.png"
  metadata: {             // Métadonnées de génération
    model: string;
    loras: LoRARequest[];
    steps: number;
    guidance_scale: number;
    seed: number | null;
    ip_strength: number;
  }
}
```

#### ProgressMeta

```typescript
{
  step?: string;         // Ex: "generation_gpu"
  progress?: number;     // Pourcentage (0-100)
}
```

---

## Codes d'Erreur

### HTTP Status Codes

| Code | Nom | Description | Action |
|------|-----|-------------|--------|
| 200 | OK | Requête réussie | - |
| 201 | Created | Tâche créée | Récupérer `job_id` |
| 202 | Accepted | Traitement en cours | Réessayer plus tard |
| 404 | Not Found | Ressource introuvable | Vérifier job_id/filename |
| 500 | Internal Server Error | Erreur serveur | Vérifier logs |
| 503 | Service Unavailable | Queue pleine | Attendre et réessayer |

### Erreurs Spécifiques

#### Queue Pleine (503)

```json
{
  "detail": "Queue pleine, réessayez plus tard"
}
```

**Cause** : Plus de 100 jobs en attente
**Solution** : Attendre quelques minutes et réessayer

#### CUDA Out of Memory (500)

```json
{
  "detail": {
    "status": "failed",
    "error": "CUDA out of memory"
  }
}
```

**Cause** : GPU saturé (rare avec les optimisations actuelles)
**Solution** : Réessayer, la tâche est automatiquement retentée 3 fois

#### Job ID Invalide (404)

```json
{
  "detail": "Job ID non trouvé"
}
```

**Cause** : Job ID inexistant ou expiré (>1h)
**Solution** : Vérifier le job ID ou créer une nouvelle génération

---

## Exemples Pratiques

### Workflow Simple (Python)

```python
import requests
import time

API_URL = "http://localhost:8009"

# 1. Créer une génération
response = requests.post(f"{API_URL}/generate", json={
    "prompt": "a beautiful landscape with mountains and lake",
    "negative_prompt": "blurry, low quality"
})

job_id = response.json()["job_id"]
print(f"Job créé: {job_id}")

# 2. Polling du statut
while True:
    response = requests.get(f"{API_URL}/status/{job_id}")
    data = response.json()

    if data["status"] == "SUCCESS":
        filename = data["result"]["filename"]
        print(f"✅ Génération terminée: {filename}")
        break
    elif data["status"] == "FAILURE":
        print(f"❌ Échec: {data['error']}")
        break
    else:
        print(f"⏳ Status: {data['status']}")
        time.sleep(5)

# 3. Télécharger l'image
response = requests.get(f"{API_URL}/download/{filename}")
with open("output.png", "wb") as f:
    f.write(response.content)
print("✅ Image téléchargée: output.png")
```

### Workflow Simplifié avec /image/{job_id}

```python
import requests
import time

API_URL = "http://localhost:8009"

# 1. Créer une génération
response = requests.post(f"{API_URL}/generate", json={
    "prompt": "a cute robot"
})
job_id = response.json()["job_id"]

# 2. Polling direct sur /image/{job_id}
while True:
    response = requests.get(f"{API_URL}/image/{job_id}")

    if response.status_code == 200:
        # Image prête !
        with open("robot.png", "wb") as f:
            f.write(response.content)
        print("✅ Image téléchargée: robot.png")
        break
    elif response.status_code == 202:
        # En cours
        print("⏳ Génération en cours...")
        time.sleep(5)
    else:
        # Erreur
        print(f"❌ Erreur: {response.status_code}")
        print(response.json())
        break
```

### Batch Generation (Bash)

```bash
#!/bin/bash

API_URL="http://localhost:8009"
PROMPTS=(
  "a dragon in the sky"
  "a forest at night"
  "a futuristic city"
)

for i in "${!PROMPTS[@]}"; do
  PROMPT="${PROMPTS[$i]}"

  # Créer job
  JOB_ID=$(curl -s -X POST "$API_URL/generate" \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": \"$PROMPT\"}" \
    | jq -r '.job_id')

  echo "[$i] Job créé: $JOB_ID"

  # Attendre et télécharger
  while ! curl -f -o "image_$i.png" "$API_URL/image/$JOB_ID" 2>/dev/null; do
    sleep 5
  done

  echo "[$i] ✅ Téléchargé: image_$i.png"
done

echo "✅ Toutes les images générées!"
```

### Style Transfer avec IP-Adapter

```bash
# Placer une image de référence dans reference/my_style.png
# Puis générer avec ip_strength > 0

curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a fantasy castle",
    "negative_prompt": "blurry",
    "ip_strength": 0.7
  }'
```

**Note** : L'image de référence doit être configurée dans le serveur (`reference/electra_ref.png` par défaut).

### Génération avec LoRA (Python)

```python
import requests
import time

API_URL = "http://localhost:8009"

# Génération avec un LoRA anime style
response = requests.post(f"{API_URL}/generate", json={
    "prompt": "a cute anime character with detailed eyes",
    "negative_prompt": "blurry, bad anatomy",
    "model": "sdxl-base",
    "loras": [
        {
            "name": "anime-style",
            "weight": 0.75
        }
    ],
    "steps": 35,
    "guidance_scale": 8.0,
    "seed": 42  # Pour reproductibilité
})

job_id = response.json()["job_id"]
print(f"Job créé: {job_id}")

# Polling jusqu'à succès
while True:
    response = requests.get(f"{API_URL}/status/{job_id}")
    data = response.json()

    if data["status"] == "SUCCESS":
        # Récupérer metadata
        metadata = data["result"]["metadata"]
        print(f"✅ Image générée avec:")
        print(f"   Model: {metadata['model']}")
        print(f"   LoRAs: {metadata['loras']}")
        print(f"   Steps: {metadata['steps']}")
        print(f"   Seed: {metadata['seed']}")

        # Télécharger l'image
        image_response = requests.get(f"{API_URL}/image/{job_id}")
        with open("anime_character.png", "wb") as f:
            f.write(image_response.content)
        print("✅ Image téléchargée: anime_character.png")
        break

    elif data["status"] == "FAILURE":
        print(f"❌ Échec: {data['error']}")
        break

    else:
        print(f"⏳ Status: {data['status']}")
        time.sleep(5)
```

### Multi-LoRA Generation (cURL)

```bash
# Combiner plusieurs LoRAs pour un style unique
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "cyberpunk character with neon outfit in a futuristic city",
    "negative_prompt": "blurry, low quality, bad anatomy",
    "model": "sdxl-base",
    "loras": [
      {
        "name": "anime-style",
        "weight": 0.6
      },
      {
        "name": "character-detail",
        "weight": 0.8
      }
    ],
    "steps": 40,
    "guidance_scale": 8.5,
    "seed": 12345
  }'
```

### Reproductibilité avec Seed (Python)

```python
import requests

API_URL = "http://localhost:8009"

# Générer la même image deux fois avec le même seed
params = {
    "prompt": "a majestic dragon flying over mountains",
    "model": "sdxl-base",
    "steps": 30,
    "guidance_scale": 7.5,
    "seed": 999  # Même seed = même résultat
}

# Première génération
job1 = requests.post(f"{API_URL}/generate", json=params).json()["job_id"]

# Deuxième génération (identique)
job2 = requests.post(f"{API_URL}/generate", json=params).json()["job_id"]

print(f"Les deux jobs produiront exactement la même image!")
print(f"Job 1: {job1}")
print(f"Job 2: {job2}")
```

### Découvrir les Modèles et LoRAs Disponibles

```bash
# Lister les modèles disponibles
curl http://localhost:8009/models | jq '.models[] | {id, name, description}'

# Lister les LoRAs disponibles
curl http://localhost:8009/loras | jq '.loras[] | {id, name, default_weight, trigger_words}'

# Exemple de sortie:
# {
#   "id": "anime-style",
#   "name": "Anime Style Enhancer",
#   "default_weight": 0.75,
#   "trigger_words": ["anime style", "detailed"]
# }
```

---

## Limites & Quotas

### Limites Actuelles

| Limite | Valeur | Description |
|--------|--------|-------------|
| **Queue Max** | 100 jobs | Maximum de tâches en attente |
| **Timeout** | 10 minutes | Timeout par génération |
| **Retry** | 3 tentatives | Retry automatique sur erreur |
| **Result TTL** | 1 heure | Durée de conservation des résultats |
| **Concurrent Workers** | 1 | Une génération à la fois (GPU limité) |
| **Image Size** | 1024x1024 | Résolution fixe (SDXL native) |
| **Steps Range** | 10-100 | Nombre d'itérations de diffusion (défaut: 30) |
| **Guidance Scale Range** | 1.0-30.0 | CFG scale pour le respect du prompt (défaut: 7.5) |
| **Max LoRAs** | 3-4 simultanés | Limitation VRAM (11GB GPU) |
| **Seed Range** | null ou int | null = aléatoire, int = reproductible |

### Performance

| Métrique | Valeur Moyenne |
|----------|----------------|
| **Temps de Génération** | ~4-5 minutes |
| **VRAM Utilisée** | ~10-11 GB |
| **Taille Image** | ~1-2 MB (PNG) |
| **Throughput** | ~14 images/heure |

### Recommandations

1. **Polling Interval** : 5-10 secondes pour vérifier le statut
2. **Prompt Length** : Illimité grâce à Compel, mais <1000 caractères recommandé
3. **Negative Prompt** : Toujours fournir pour meilleure qualité
4. **IP Strength** : 0.5-0.7 pour équilibre style/prompt

---

## Notes Techniques

### Format des Fichiers

- **Format** : PNG
- **Résolution** : 1024x1024 pixels
- **Profondeur** : 8 bits par canal (RGB)
- **Taille** : ~1-2 MB

### Nommage des Fichiers

```
{model_prefix}_{timestamp}_{unique_id}.png

Exemple: sdxl_base_20260130_123456_abc123.png
         │         │         │       └─ UUID court (8 chars)
         │         │         └─ Heure (HHMMSS)
         │         └─ Date (YYYYMMDD)
         └─ Préfixe du modèle (ex: sdxl_base, pony_xl_v6)
```

**Note** : Le préfixe du modèle permet d'identifier rapidement quel modèle a généré l'image.

### Expiration des Résultats

Les résultats (statut et images) sont conservés **1 heure** après génération.
Après expiration :
- Le statut retournera `PENDING` (comme si le job n'existait pas)
- Les fichiers restent dans `/outputs` mais le lien est perdu

**Recommandation** : Télécharger les images immédiatement après génération.

---

## Versioning & Changelog

### Version 2.0 (Actuelle) - 2026-01-30

**Nouveaux Endpoints** :
- ✨ `GET /models` - Liste des modèles disponibles
- ✨ `GET /loras` - Liste des LoRAs disponibles

**Endpoints Étendus** :
- ✅ `POST /generate` - Support multi-modèles, LoRAs, steps, guidance_scale, seed
- ✅ `GET /status/{job_id}` - Retourne metadata de génération
- ✅ `GET /image/{job_id}` - Header X-Generation-Metadata avec paramètres

**Nouvelles Features** :
- ✨ **Multi-modèles** - Sélection du modèle base (SDXL, PonyXL, etc.)
- ✨ **LoRA/LyCORIS** - Support jusqu'à 3-4 LoRAs simultanés
- ✨ **Paramètres avancés** - steps (10-100), guidance_scale (1.0-30.0)
- ✨ **Reproductibilité** - Seed pour générations identiques
- ✨ **Trigger words** - Auto-injection des trigger words des LoRAs
- ✨ **Metadata** - Métadonnées complètes dans les résultats

**Breaking Changes** :
- ❌ **Aucun** - Backward compatible avec v1.0

---

### Version 1.0 - 2026-01-29

**Endpoints** :
- ✅ `POST /generate` - Création de tâches
- ✅ `GET /status/{job_id}` - Vérification de statut
- ✅ `GET /image/{job_id}` - Téléchargement direct par job ID
- ✅ `GET /download/{filename}` - Téléchargement par nom de fichier
- ✅ `GET /health` - Health check

**Features** :
- ✅ Génération SDXL Base 1.0
- ✅ Support prompts longs (Compel)
- ✅ IP-Adapter (style transfer)
- ✅ Queue asynchrone (Celery + Redis)
- ✅ Retry automatique (3x)

---

## Support & Contact

### Documentation Complémentaire

- **[WORKFLOW.md](WORKFLOW.md)** - Architecture détaillée du système
- **[CLAUDE.md](CLAUDE.md)** - Documentation projet complète
- **[API_UPDATES.md](API_UPDATES.md)** - Mises à jour et nouveautés

### Dépannage

**L'API ne répond pas** :
```bash
# Vérifier le health check
curl http://localhost:8009/health

# Vérifier les conteneurs
docker-compose ps

# Vérifier les logs
docker-compose logs api
```

**Queue pleine (503)** :
```bash
# Vérifier combien de jobs sont en attente
curl http://localhost:8009/status/{job_id}

# Attendre que la queue se vide
```

**Génération échouée (FAILURE)** :
```bash
# Vérifier les logs du worker
docker-compose logs worker --tail=50

# Les erreurs communes sont automatiquement retentées 3x
```

---

## Exemples cURL Complets

### Génération Simple

```bash
# 1. Créer
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a serene lake surrounded by mountains at dawn, mist rising from water, soft golden light",
    "negative_prompt": "blurry, low quality, distorted, ugly, bad composition"
  }' | jq '.'

# Réponse:
# {
#   "job_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "queued",
#   "message": "Tâche en file d'attente. Position estimée: 1"
# }

# 2. Vérifier (après 30s)
curl http://localhost:8009/status/550e8400-e29b-41d4-a716-446655440000 | jq '.'

# 3. Télécharger (après ~5 min)
curl http://localhost:8009/image/550e8400-e29b-41d4-a716-446655440000 \
  -o lake_mountains.png
```

### Génération avec Style Transfer

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cyberpunk street at night with neon signs",
    "negative_prompt": "blurry, low quality",
    "ip_strength": 0.65
  }' | jq -r '.job_id'
```

### Génération v2.0 avec LoRAs et Seed

```bash
# Génération avancée avec LoRA, steps personnalisés et seed
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cute anime girl with detailed face and eyes, fantasy outfit",
    "negative_prompt": "blurry, bad anatomy, low quality",
    "model": "sdxl-base",
    "loras": [
      {
        "name": "anime-style",
        "weight": 0.75
      },
      {
        "name": "character-detail",
        "weight": 0.6
      }
    ],
    "steps": 35,
    "guidance_scale": 8.0,
    "seed": 42
  }' | jq '.'

# Réponse inclut le job_id
# Télécharger l'image quand prête:
# curl http://localhost:8009/image/{job_id} -o result.png

# Header X-Generation-Metadata contiendra:
# {"model": "sdxl-base", "loras": [...], "steps": 35, "guidance_scale": 8.0, "seed": 42, ...}
```

---

**API Version** : 2.0
**Dernière mise à jour** : 2026-01-30
**Statut** : Production Ready ✅
**Backward Compatible** : ✅ Oui (avec v1.0)
