# 🚀 Quickstart v2.0 - Multi-Modèles & LoRAs

Guide rapide pour utiliser les nouvelles fonctionnalités v2.0.

---

## 🔑 0. Configuration Optionnelle : Tokens API

**Pour modèles privés/gated** : Voir [API_TOKENS_GUIDE.md](API_TOKENS_GUIDE.md)

```bash
# Créer le fichier .env
cp .env.example .env

# Éditer et ajouter vos tokens (optionnel)
nano .env
```

**Exemple** : `.env`
```bash
HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
CIVITAI_API_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Avantages** :
- ✅ Accès aux modèles HuggingFace privés/gated
- ✅ Pas de limite de téléchargement
- ✅ Accès aux LoRAs privés

**Rebuild après configuration** :
```bash
docker-compose down
docker-compose up -d
```

---

## 📦 1. Ajouter un Nouveau Modèle (ex: PonyXL v6)

### Option A : Auto-téléchargement depuis HuggingFace

**Fichier** : `app/models_config.py`

```python
AVAILABLE_MODELS = {
    "sdxl-base": ModelConfig(...),  # Déjà configuré

    # Décommenter pour activer PonyXL
    "pony-xl-v6": ModelConfig(
        name="PonyXL v6",
        path="AstraliteHeart/pony-diffusion-v6-xl",
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        default_negative="low quality, bad anatomy, worst quality, low res",
        description="SDXL fine-tuné pour style anime/pony"
    ),
}
```

**Rebuild** :
```bash
docker-compose restart worker
```

Le modèle sera téléchargé au **premier usage** (~6.5GB).

### Option B : Modèle local

1. **Télécharger** le modèle dans `./models/pony-xl-v6/`
2. **Configurer** dans `models_config.py` :
```python
"pony-xl-v6": ModelConfig(
    name="PonyXL v6",
    path="./models/pony-xl-v6",  # Chemin local
    vae_path="madebyollin/sdxl-vae-fp16-fix",
    default_negative="low quality, bad anatomy",
    description="PonyXL local"
),
```

---

## 🎨 2. Ajouter un LoRA Custom (ex: depuis Civitai)

### Exemple : LoRA Civitai

**URL Civitai** : `https://civitai.com/api/download/models/695220?type=Model&format=SafeTensor`

#### Étape 1 : Télécharger le LoRA

```bash
# Créer le dossier
mkdir -p ./models/my_custom_lora

# Télécharger (depuis le host, PAS le DevContainer)
cd /mnt/c/Users/TON_USER/path/to/imagen  # Adapter selon ton setup
wget -O ./models/my_custom_lora/model.safetensors \
  "https://civitai.com/api/download/models/695220?type=Model&format=SafeTensor"
```

**Alternative** : Télécharger manuellement et placer dans `./models/my_custom_lora/`

#### Étape 2 : Configurer dans `app/models_config.py`

```python
AVAILABLE_LORAS = {
    # LoRAs existants...
    "anime-style": LoRAConfig(...),
    "character-detail": LoRAConfig(...),

    # Nouveau LoRA custom
    "my-civitai-lora": LoRAConfig(
        name="My Civitai LoRA",
        path="./models/my_custom_lora",  # Chemin local
        default_weight=0.8,
        trigger_words=["specific trigger", "keywords"],  # Vérifier sur Civitai
        description="LoRA téléchargé depuis Civitai (Model 695220)"
    ),
}
```

#### Étape 3 : Rebuild

```bash
docker-compose restart worker
```

---

## 🧪 3. Utiliser PonyXL + LoRA Custom

### Via API (cURL)

```bash
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cute pony character with detailed eyes, fantasy background",
    "negative_prompt": "low quality, bad anatomy, worst quality",
    "model": "pony-xl-v6",
    "loras": [
      {
        "name": "my-civitai-lora",
        "weight": 0.8
      }
    ],
    "steps": 35,
    "guidance_scale": 7.5,
    "seed": 42
  }'
```

**Réponse** :
```json
{
  "job_id": "abc12345-...",
  "status": "queued",
  "message": "Tâche en file d'attente"
}
```

### Via Python

```python
import requests
import time

API_URL = "http://localhost:8009"

# Créer la génération
response = requests.post(f"{API_URL}/generate", json={
    "prompt": "a cute pony character with detailed eyes",
    "negative_prompt": "low quality, bad anatomy",
    "model": "pony-xl-v6",
    "loras": [
        {"name": "my-civitai-lora", "weight": 0.8}
    ],
    "steps": 35,
    "guidance_scale": 7.5,
    "seed": 42
})

job_id = response.json()["job_id"]
print(f"Job créé: {job_id}")

# Polling jusqu'à complétion
while True:
    status = requests.get(f"{API_URL}/status/{job_id}").json()

    if status["status"] == "SUCCESS":
        print(f"✅ Image prête: {status['result']['filename']}")

        # Télécharger l'image
        image = requests.get(f"{API_URL}/image/{job_id}")
        with open("pony_output.png", "wb") as f:
            f.write(image.content)
        print("✅ Image téléchargée: pony_output.png")
        break

    elif status["status"] == "FAILURE":
        print(f"❌ Erreur: {status['error']}")
        break

    else:
        print(f"⏳ Status: {status['status']}")
        time.sleep(5)
```

---

## 🔍 4. Vérifier les Modèles et LoRAs Disponibles

### Lister les modèles

```bash
curl http://localhost:8009/models | jq '.'
```

**Réponse** :
```json
{
  "models": [
    {
      "id": "sdxl-base",
      "name": "SDXL Base 1.0",
      "description": "..."
    },
    {
      "id": "pony-xl-v6",
      "name": "PonyXL v6",
      "description": "..."
    }
  ]
}
```

### Lister les LoRAs

```bash
curl http://localhost:8009/loras | jq '.'
```

**Réponse** :
```json
{
  "loras": [
    {
      "id": "my-civitai-lora",
      "name": "My Civitai LoRA",
      "default_weight": 0.8,
      "trigger_words": ["specific trigger", "keywords"]
    }
  ]
}
```

---

## ⚙️ 5. Workflow Complet : PonyXL + LoRA Civitai

### Résumé des Étapes

1. **Télécharger le LoRA** :
   ```bash
   mkdir -p ./models/civitai_lora_695220
   wget -O ./models/civitai_lora_695220/model.safetensors \
     "https://civitai.com/api/download/models/695220?type=Model&format=SafeTensor"
   ```

2. **Éditer `app/models_config.py`** :
   - Décommenter `pony-xl-v6` dans `AVAILABLE_MODELS`
   - Ajouter le LoRA dans `AVAILABLE_LORAS` :
     ```python
     "civitai-695220": LoRAConfig(
         name="Civitai LoRA 695220",
         path="./models/civitai_lora_695220",
         default_weight=0.8,
         trigger_words=None,  # Vérifier sur la page Civitai
         description="Custom LoRA from Civitai"
     ),
     ```

3. **Rebuild le worker** :
   ```bash
   docker-compose restart worker
   ```

4. **Vérifier que tout est détecté** :
   ```bash
   curl http://localhost:8009/models | jq '.models[].id'
   # Devrait afficher: "sdxl-base" et "pony-xl-v6"

   curl http://localhost:8009/loras | jq '.loras[].id'
   # Devrait afficher: "anime-style", "character-detail", "civitai-695220"
   ```

5. **Générer une image** :
   ```bash
   curl -X POST http://localhost:8009/generate \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "your prompt here",
       "model": "pony-xl-v6",
       "loras": [{"name": "civitai-695220", "weight": 0.8}],
       "steps": 30,
       "seed": 42
     }' | jq '.job_id'
   ```

6. **Récupérer l'image** :
   ```bash
   # Remplacer JOB_ID par le job_id retourné
   curl http://localhost:8009/image/JOB_ID -o result.png
   ```

---

## 📋 Checklist Rapide

- [ ] Télécharger le LoRA dans `./models/mon_lora/`
- [ ] Ajouter le LoRA dans `app/models_config.py`
- [ ] (Optionnel) Décommenter PonyXL dans `models_config.py`
- [ ] Rebuild: `docker-compose restart worker`
- [ ] Vérifier: `curl http://localhost:8009/loras`
- [ ] Générer: `POST /generate` avec `"model": "pony-xl-v6"` et `"loras": [...]`

---

## ⚠️ Notes Importantes

### VRAM

- **SDXL base** : ~6.5 GB
- **+ 1 LoRA** : +0.3 GB
- **+ 3 LoRAs** : +0.8 GB
- **Limite GPU** : 11 GB (RTX 2080 Ti)

**Recommandation** : Max 3-4 LoRAs simultanés

### Téléchargement de Modèles

- **HuggingFace** : Auto-téléchargement au premier usage
- **Civitai/Local** : Téléchargement manuel requis

### Trigger Words

- Vérifier sur la **page Civitai du LoRA** les trigger words recommandés
- Les ajouter dans `trigger_words` pour auto-injection dans le prompt

### DevContainer + Docker-from-Docker

⚠️ **IMPORTANT** : Télécharger les modèles **depuis le host Windows**, PAS depuis le DevContainer !

```bash
# ❌ NE PAS FAIRE (depuis DevContainer):
wget -O ./models/lora.safetensors https://...

# ✅ FAIRE (depuis Windows ou WSL host):
cd /mnt/c/Users/TON_USER/path/to/imagen
wget -O ./models/mon_lora/lora.safetensors https://...
```

Raison : Docker-from-Docker + volumes bind = namespace isolation.

---

## 🎯 Exemple Complet : Setup PonyXL + LoRA en 5 Minutes

```bash
# 1. Télécharger le LoRA (depuis le host)
mkdir -p ./models/my_lora
wget -O ./models/my_lora/model.safetensors \
  "https://civitai.com/api/download/models/695220?type=Model&format=SafeTensor"

# 2. Éditer models_config.py
# - Décommenter pony-xl-v6
# - Ajouter le LoRA dans AVAILABLE_LORAS

# 3. Rebuild
docker-compose restart worker

# 4. Vérifier
curl http://localhost:8009/models | jq '.models[].id'

# 5. Générer
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cute anime pony",
    "model": "pony-xl-v6",
    "loras": [{"name": "my-lora", "weight": 0.8}],
    "seed": 42
  }' | jq -r '.job_id'

# 6. Attendre ~5 min et télécharger
# curl http://localhost:8009/image/JOB_ID -o result.png
```

---

**Documentation complète** : [API.md](API.md)
**Troubleshooting** : [V2_IMPLEMENTATION_SUMMARY.md](V2_IMPLEMENTATION_SUMMARY.md)
