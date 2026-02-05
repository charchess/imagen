#!/bin/bash

# Script de génération d'images interactif pour Imagen (Version améliorée)
# Usage: ./generate.sh

set -eo pipefail

DOCKER_OUTPUTS="/workspace/outputs"
LOCAL_OUTPUTS="/workspaces/imagen/outputs"
MAX_RETRIES=3
TIMEOUT=600  # 10 minutes max

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les erreurs
error() {
    echo -e "${RED}❌ Erreur: $1${NC}" >&2
}

# Fonction pour afficher les succès
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Fonction pour afficher les infos
info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Fonction pour afficher les warnings
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo "🎨 Imagen - Générateur d'images interactif (v2.0)"
echo "=================================================="
echo ""

# ============================================
# 1. DÉTECTION AUTOMATIQUE DE L'IP DE L'API
# ============================================
info "Détection de l'API Docker..."
API_IP=$(docker inspect imagen-api-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)

if [ -z "$API_IP" ]; then
    error "Impossible de trouver l'IP du conteneur API"
    echo ""
    echo "Vérifications possibles:"
    echo "  1. docker-compose ps"
    echo "  2. docker-compose up -d"
    exit 1
fi

API_URL="http://$API_IP:8000"
success "API trouvée à $API_URL"
echo ""

# ============================================
# 2. TEST DE CONNEXION À L'API
# ============================================
info "Test de connexion à l'API..."
HEALTH_CHECK=$(curl -s --connect-timeout 5 "$API_URL/health" 2>/dev/null || echo "")

if [ -z "$HEALTH_CHECK" ]; then
    error "L'API ne répond pas"
    echo ""
    echo "Diagnostics:"
    echo "  - Vérifiez que l'API est démarrée: docker-compose logs api --tail 20"
    echo "  - Redémarrez si nécessaire: docker-compose restart api"
    exit 1
fi

GPU_STATUS=$(echo "$HEALTH_CHECK" | python3 -c "import sys, json; print(json.load(sys.stdin).get('gpu_available', False))" 2>/dev/null)
success "API connectée (GPU: $GPU_STATUS)"
echo ""

# ============================================
# 3. COLLECTE DES PARAMÈTRES
# ============================================

# 3.1. Prompt positif
echo "📝 Prompt positif (description de l'image):"
read -r PROMPT
if [ -z "$PROMPT" ]; then
    error "Le prompt ne peut pas être vide"
    exit 1
fi
echo ""

# 3.2. Prompt négatif
echo "🚫 Prompt négatif (optionnel, appuyez sur Entrée pour valeur par défaut):"
read -r NEGATIVE_PROMPT
if [ -z "$NEGATIVE_PROMPT" ]; then
    NEGATIVE_PROMPT="low quality, blurry, worst quality"
fi
echo ""

# 3.3. Modèle
echo "🤖 Modèle à utiliser:"
echo "  1) sdxl (Stable Diffusion XL - réaliste)"
echo "  2) pony (Pony Diffusion v6 - anime/furry)"
read -p "Choisissez (1 ou 2): " MODEL_CHOICE
case $MODEL_CHOICE in
    1) MODEL="sdxl" ;;
    2) MODEL="pony" ;;
    *) MODEL="pony" ;;
esac
success "Modèle: $MODEL"
echo ""

# 3.4. Image de référence
echo "🖼️  Image de référence (optionnel):"
echo "  Voulez-vous utiliser une image de référence pour le transfert de style ?"
read -p "  (o/N): " USE_REFERENCE
IP_STRENGTH=0.0

if [[ "$USE_REFERENCE" =~ ^[oOyY]$ ]]; then
    echo "  Chemin de l'image de référence:"
    echo "  (doit être dans /workspaces/imagen/reference/)"
    read -r REFERENCE_PATH

    if [ -n "$REFERENCE_PATH" ]; then
        REFERENCE_FILENAME=$(basename "$REFERENCE_PATH")
        read -p "  Force du transfert de style (0.0-1.0, défaut: 0.6): " IP_STRENGTH_INPUT
        IP_STRENGTH=${IP_STRENGTH_INPUT:-0.6}
        success "Référence: $REFERENCE_FILENAME (force: $IP_STRENGTH)"
    fi
fi
echo ""

# 3.5. LoRAs
echo "🔧 LoRAs (optionnel):"
echo "  Entrez les IDs des LoRAs séparés par des virgules"
echo "  Exemple: civitai-618068"
echo "  (Appuyez sur Entrée pour aucun LoRA)"
read -r LORA_INPUT
echo ""

# 3.6. Steps et guidance
echo "⚙️  Paramètres avancés (optionnel, Entrée pour valeurs par défaut):"
read -p "  Steps (défaut: 30): " STEPS
STEPS=${STEPS:-30}
read -p "  Guidance scale (défaut: 7.5): " GUIDANCE
GUIDANCE=${GUIDANCE:-7.5}
echo ""

# ============================================
# 4. RÉCAPITULATIF
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Récapitulatif de la génération"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Prompt: ${PROMPT:0:60}..."
echo "  Modèle: $MODEL"
echo "  Steps: $STEPS"
echo "  Guidance: $GUIDANCE"
if [ -n "$LORA_INPUT" ]; then
    echo "  LoRAs: $LORA_INPUT"
fi
if [ "$IP_STRENGTH" != "0.0" ] && [ "$IP_STRENGTH" != "0" ]; then
    echo "  Style transfer: $IP_STRENGTH"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Continuer ? (O/n): " CONFIRM
if [[ "$CONFIRM" =~ ^[nN]$ ]]; then
    warning "Génération annulée"
    exit 0
fi
echo ""

# ============================================
# 5. CONSTRUCTION DE LA REQUÊTE JSON
# ============================================
JSON_DATA="{
  \"prompt\": \"$PROMPT\",
  \"negative_prompt\": \"$NEGATIVE_PROMPT\",
  \"model\": \"$MODEL\",
  \"steps\": $STEPS,
  \"guidance_scale\": $GUIDANCE,
  \"ip_strength\": $IP_STRENGTH"

# Ajouter les LoRAs si spécifiés
if [ -n "$LORA_INPUT" ]; then
    LORAS_JSON="["
    IFS=',' read -ra LORA_ARRAY <<< "$LORA_INPUT"
    for i in "${!LORA_ARRAY[@]}"; do
        LORA_ID=$(echo "${LORA_ARRAY[$i]}" | xargs)
        if [ $i -gt 0 ]; then LORAS_JSON+=","; fi
        LORAS_JSON+="{\"name\": \"$LORA_ID\", \"weight\": 0.8}"
    done
    LORAS_JSON+="]"
    JSON_DATA+=",
  \"loras\": $LORAS_JSON"
fi

JSON_DATA+="
}"

# ============================================
# 6. SOUMISSION DE LA GÉNÉRATION
# ============================================
info "Envoi de la requête à l'API..."
START_TIME=$(date +%s)

RESPONSE=$(curl -s --connect-timeout 10 -X POST "$API_URL/generate" \
  -H "Content-Type: application/json" \
  -d "$JSON_DATA" 2>/dev/null)

JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    error "Échec de la soumission"
    echo ""
    echo "Réponse de l'API:"
    echo "$RESPONSE"
    exit 1
fi

success "Job créé: $JOB_ID"
echo ""

# ============================================
# 7. SUIVI DE PROGRESSION AVANCÉ
# ============================================
info "Génération en cours..."
echo ""

DOTS=""
RETRY_COUNT=0
ELAPSED=0

# Trap pour gérer Ctrl+C proprement
trap 'echo ""; warning "Génération annulée par l'\''utilisateur"; exit 130' INT

while true; do
    STATUS_RESPONSE=$(curl -s --connect-timeout 5 "$API_URL/status/$JOB_ID" 2>/dev/null || echo "")

    if [ -z "$STATUS_RESPONSE" ]; then
        ((RETRY_COUNT++))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo ""
            error "Impossible de contacter l'API après $MAX_RETRIES tentatives"
            exit 1
        fi
        warning "Erreur de connexion, nouvelle tentative ($RETRY_COUNT/$MAX_RETRIES)..."
        sleep 3
        continue
    fi

    RETRY_COUNT=0
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null)

    # Calculer le temps écoulé
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    # Timeout
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo ""
        error "Timeout: la génération a pris plus de $((TIMEOUT/60)) minutes"
        exit 1
    fi

    if [ "$STATUS" = "SUCCESS" ]; then
        FILENAME=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['filename'])")
        break
    elif [ "$STATUS" = "FAILURE" ]; then
        ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', 'Unknown error'))")
        echo ""
        error "Échec de la génération: $ERROR"
        exit 1
    elif [ "$STATUS" = "PROGRESS" ]; then
        STEP=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('meta', {}).get('step', 'processing'))" 2>/dev/null || echo "processing")
        PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('meta', {}).get('progress', 0))" 2>/dev/null || echo "0")

        # Barre de progression
        PERCENT=$PROGRESS
        BAR_LENGTH=30
        FILLED=$((PERCENT * BAR_LENGTH / 100))
        EMPTY=$((BAR_LENGTH - FILLED))
        BAR=$(printf "%${FILLED}s" | tr ' ' '█')
        BAR="${BAR}$(printf "%${EMPTY}s" | tr ' ' '░')"

        echo -ne "\r⏳ [$BAR] $PERCENT% - $STEP (${ELAPSED}s)   "
    else
        echo -ne "\r⏳ En attente$DOTS (${ELAPSED}s)   "
    fi

    DOTS="${DOTS}."
    if [ ${#DOTS} -gt 3 ]; then DOTS=""; fi
    sleep 2
done

echo ""
echo ""

# ============================================
# 8. COPIE DU FICHIER
# ============================================
info "Copie du fichier généré..."

mkdir -p "$LOCAL_OUTPUTS"

if [ ! -f "$DOCKER_OUTPUTS/$FILENAME" ]; then
    error "Le fichier n'a pas été trouvé dans le volume Docker"
    exit 1
fi

cp "$DOCKER_OUTPUTS/$FILENAME" "$LOCAL_OUTPUTS/"
LOCAL_PATH="$LOCAL_OUTPUTS/$FILENAME"

# Taille du fichier
FILE_SIZE=$(du -h "$LOCAL_PATH" | cut -f1)

# Temps total
TOTAL_TIME=$ELAPSED

echo ""
success "C'est prêt!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Résumé"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📁 Fichier: $FILENAME"
echo "  📐 Taille: $FILE_SIZE"
echo "  ⏱️  Durée: ${TOTAL_TIME}s"
echo "  📍 Chemin: $LOCAL_PATH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🖼️  Pour voir l'image:"
echo "   - VSCode: Ctrl+P puis tapez: $FILENAME"
echo "   - Terminal: xdg-open \"$LOCAL_PATH\""
echo ""

# Option pour ouvrir automatiquement
read -p "Ouvrir l'image maintenant ? (o/N): " OPEN_IMAGE
if [[ "$OPEN_IMAGE" =~ ^[oOyY]$ ]]; then
    xdg-open "$LOCAL_PATH" 2>/dev/null &
    success "Image ouverte"
fi

echo ""
