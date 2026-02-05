# 🔑 Guide des Tokens API

Guide pour configurer les tokens HuggingFace et Civitai pour faciliter le téléchargement de modèles et LoRAs.

---

## 📋 Table des Matières

- [HuggingFace Token](#huggingface-token)
- [Civitai API Token](#civitai-api-token)
- [Configuration](#configuration)
- [Cas d'Usage](#cas-dusage)

---

## 🤗 HuggingFace Token

### Pourquoi ?

Le token HuggingFace permet de :
- ✅ Télécharger des **modèles privés** (vos propres modèles)
- ✅ Accéder aux **modèles gated** (modèles nécessitant acceptation de licence)
- ✅ Augmenter la **limite de téléchargement** (pour gros modèles)

### Obtenir le Token

1. **Créer un compte** sur [HuggingFace](https://huggingface.co)
2. **Aller dans les paramètres** : https://huggingface.co/settings/tokens
3. **Créer un nouveau token** :
   - Type : **Read** (lecture seule suffit)
   - Nom : `imagen-api` (ou autre)
4. **Copier le token** (commence par `hf_...`)

**Important** : Ne jamais partager ou commiter ce token dans Git !

---

## 🎨 Civitai API Token

### Pourquoi ?

Le token Civitai API permet de :
- ✅ Télécharger des **modèles/LoRAs directement via API**
- ✅ Accéder à vos **modèles privés** Civitai
- ⚠️ **Note** : Nécessite un script custom (non implémenté par défaut)

### Obtenir le Token

1. **Créer un compte** sur [Civitai](https://civitai.com)
2. **Aller dans les paramètres** : https://civitai.com/user/account
3. **Section "API Keys"**
4. **Créer une nouvelle clé** et copier

---

## ⚙️ Configuration

### 1. Créer le fichier `.env`

```bash
# Copier le template
cp .env.example .env

# Éditer le fichier
nano .env  # ou vim, code, etc.
```

### 2. Ajouter les Tokens

**Fichier** : `.env`

```bash
# HuggingFace Token (pour modèles privés/gated)
HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Civitai API Token (optionnel, pour auto-download futur)
CIVITAI_API_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Rebuild les Containers

```bash
# Les containers vont maintenant charger le .env
docker-compose down
docker-compose up -d

# Vérifier les logs
docker-compose logs worker | grep "token"
# Devrait afficher: "🔑 Utilisation du token HuggingFace"
```

---

## 🎯 Cas d'Usage

### 1. Modèle HuggingFace Privé

**Scénario** : Vous avez entraîné un modèle custom sur HuggingFace (privé).

**Configuration** : `app/models_config.py`

```python
AVAILABLE_MODELS = {
    "my-custom-model": ModelConfig(
        name="My Custom Model",
        path="username/my-private-sdxl-model",  # Repo privé
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        default_negative="low quality",
        description="Mon modèle custom privé"
    ),
}
```

**Sans token** : ❌ Erreur 401 Unauthorized

**Avec token** : ✅ Téléchargement automatique

---

### 2. Modèle Gated (ex: Llama, SD3)

**Scénario** : Certains modèles nécessitent acceptation de licence.

**Exemple** : `stabilityai/stable-diffusion-3-medium`

**Étapes** :
1. Accepter la licence sur HuggingFace
2. Configurer le token dans `.env`
3. Utiliser le modèle normalement

**Sans token** : ❌ Erreur "Gated model"

**Avec token** : ✅ Accès autorisé

---

### 3. LoRA HuggingFace Privé

**Configuration** : `app/models_config.py`

```python
AVAILABLE_LORAS = {
    "my-private-lora": LoRAConfig(
        name="My Private LoRA",
        path="username/my-private-lora",  # Repo privé
        default_weight=0.8,
        trigger_words=["custom style"],
        description="Mon LoRA custom"
    ),
}
```

**Avec token** : ✅ Chargé automatiquement au premier usage

---

### 4. Auto-Download Civitai (Futur)

**Note** : Pas encore implémenté, nécessite un script custom.

**Concept** :

```python
# Script futur pour télécharger depuis Civitai
def download_civitai_lora(model_id: int, output_path: str):
    """
    Télécharge un LoRA depuis Civitai via API
    """
    import requests

    url = f"https://civitai.com/api/download/models/{model_id}"
    headers = {}

    # Utiliser le token si disponible
    if CIVITAI_API_TOKEN:
        headers["Authorization"] = f"Bearer {CIVITAI_API_TOKEN}"

    params = {"type": "Model", "format": "SafeTensor"}

    response = requests.get(url, headers=headers, params=params, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"✅ LoRA téléchargé: {output_path}")

# Usage dans models_config.py
"civitai-lora": LoRAConfig(
    name="Civitai LoRA Auto",
    path="./models/civitai_695220",
    default_weight=0.8,
    # Metadata pour auto-download
    civitai_model_id=695220
),
```

**Pour l'instant** : Téléchargement manuel requis (voir [QUICKSTART_V2.md](QUICKSTART_V2.md))

---

## 🔒 Sécurité

### ⚠️ IMPORTANT : Ne JAMAIS commiter le `.env`

**Fichier** : `.gitignore` (déjà configuré)

```bash
# Fichiers de configuration sensibles
.env
.env.local
.env.*.local
```

### Bonnes Pratiques

1. **Ne jamais partager** vos tokens
2. **Révoquer immédiatement** si compromis
3. **Utiliser des tokens Read-only** (pas Write) si possible
4. **Permissions minimales** : Seulement ce dont vous avez besoin

### Régénérer un Token

**HuggingFace** :
1. Aller sur https://huggingface.co/settings/tokens
2. Cliquer sur "Revoke" à côté de l'ancien token
3. Créer un nouveau token
4. Mettre à jour `.env`
5. Rebuild : `docker-compose restart worker`

**Civitai** :
1. Aller sur https://civitai.com/user/account
2. Supprimer l'ancienne clé
3. Créer une nouvelle
4. Mettre à jour `.env`

---

## 🧪 Tester la Configuration

### Vérifier que le Token est Chargé

```bash
# Logs du worker
docker-compose logs worker | grep "🔑"

# Devrait afficher:
# worker-1  | 🔑 Utilisation du token HuggingFace
```

### Tester avec un Modèle Gated

**Important** : Vous devez d'abord **accepter la licence** sur HuggingFace.

```python
# Dans models_config.py (exemple fictif)
AVAILABLE_MODELS = {
    "test-gated": ModelConfig(
        name="Test Gated Model",
        path="username/test-gated-model",
        vae_path="madebyollin/sdxl-vae-fp16-fix",
        default_negative="low quality",
    ),
}
```

```bash
# Rebuild
docker-compose restart worker

# Générer une image
curl -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "model": "test-gated"}'

# Vérifier les logs
docker-compose logs worker --tail 50
# Devrait télécharger sans erreur 401
```

---

## 📚 Ressources

### HuggingFace
- **Documentation Tokens** : https://huggingface.co/docs/hub/security-tokens
- **Modèles Gated** : https://huggingface.co/docs/hub/models-gated
- **API Reference** : https://huggingface.co/docs/huggingface_hub/guides/download

### Civitai
- **API Documentation** : https://github.com/civitai/civitai/wiki/REST-API-Reference
- **Download API** : https://civitai.com/api/download/models/{modelVersionId}

---

## ❓ FAQ

### Q: Le token est-il obligatoire ?

**R** : Non ! Le token est **optionnel** et seulement nécessaire pour :
- Modèles/LoRAs privés (vos propres repos)
- Modèles gated (nécessitant acceptation de licence)

Les modèles/LoRAs publics fonctionnent **sans token**.

---

### Q: Mes tokens sont-ils stockés en sécurité ?

**R** : Oui, tant que :
- ✅ Le `.env` est dans `.gitignore` (déjà fait)
- ✅ Vous ne partagez pas le fichier `.env`
- ✅ Vous n'exposez pas les variables d'environnement publiquement

Les tokens sont **uniquement** accessibles aux containers Docker locaux.

---

### Q: Puis-je utiliser plusieurs tokens HuggingFace ?

**R** : Non, un seul token à la fois. Mais vous pouvez changer de token :

```bash
# Éditer .env
nano .env

# Changer HUGGINGFACE_TOKEN
# Rebuild
docker-compose restart worker
```

---

### Q: Que faire si mon token ne fonctionne pas ?

**Checklist** :

1. **Vérifier le format** : Doit commencer par `hf_`
2. **Vérifier les permissions** : Token doit avoir accès "Read"
3. **Vérifier le `.env`** :
   ```bash
   cat .env | grep HUGGINGFACE
   # Devrait afficher: HUGGINGFACE_TOKEN=hf_xxxxx
   ```
4. **Rebuild les containers** :
   ```bash
   docker-compose down
   docker-compose up -d
   ```
5. **Vérifier les logs** :
   ```bash
   docker-compose logs worker | grep token
   ```

---

### Q: Puis-je auto-télécharger depuis Civitai ?

**R** : Pas encore implémenté nativement. Deux options :

**Option 1** : Téléchargement manuel (actuel)
```bash
wget -O ./models/lora.safetensors \
  "https://civitai.com/api/download/models/695220?type=Model&format=SafeTensor"
```

**Option 2** : Script custom (à créer)
- Voir section "Auto-Download Civitai (Futur)" ci-dessus
- Nécessite développement additionnel

---

**Dernière mise à jour** : 2026-01-30
**Version** : 2.0
