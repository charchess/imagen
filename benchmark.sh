#!/bin/bash

# Script de benchmark pour comparer modèles/LoRAs/steps/guidance
# Usage: ./benchmark.sh

set -eo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

error() { echo -e "${RED}❌ $1${NC}" >&2; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

echo "🎯 Imagen Benchmark - Comparaison de paramètres"
echo "================================================"
echo ""

# Détection API
info "Détection de l'API..."
API_IP=$(docker inspect imagen-api-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
if [ -z "$API_IP" ]; then
    error "Impossible de trouver l'API"
    exit 1
fi
API_URL="http://$API_IP:8000"
success "API: $API_URL"
echo ""

# Prompt fixe pour la comparaison
PROMPT="A beautiful anthropomorphic red fox. Classic orange and white fur, bushy tail with white tip. Emerald green eyes. Athletic but curvy silhouette. Elegant and mischievous sisterly vibe. Visage fin and expressive 狐 (fox) features. Action: un bikini sexy 1769948428. Expression: Calm, looking at viewer, serene face, neutral AUs, ears perked naturally. Attitude: Full body standing pose (plein pied), head to toe, the subject takes the full height of the image, centered in frame. high-detail soft fur texture, expressive eyes with multiple catchlights, subsurface scattering, tactile quality highly detailed, digital illustration, trending on ArtStation, award winning, masterpiece, score_9, score_8_up. Isolated on a solid flat white background, no shadows on the ground, high contrast between subject and background, centered composition, subject takes full height of frame"

NEGATIVE_PROMPT=""

# Paramètres à tester
MODELS=("pony" "sdxl")
LORA_CONFIGS=("nolora" "lora")
STEPS_CONFIGS=(30 60)
GUIDANCE_CONFIGS=(5.0 7.5 9.5)

# Calcul total
TOTAL=$((${#MODELS[@]} * ${#LORA_CONFIGS[@]} * ${#STEPS_CONFIGS[@]} * ${#GUIDANCE_CONFIGS[@]}))
CURRENT=0

echo "📊 Configuration du benchmark:"
echo "  Modèles: ${MODELS[@]}"
echo "  LoRA: ${LORA_CONFIGS[@]}"
echo "  Steps: ${STEPS_CONFIGS[@]}"
echo "  Guidance: ${GUIDANCE_CONFIGS[@]}"
echo "  Total: $TOTAL générations"
echo ""

read -p "Continuer ? (O/n): " CONFIRM
if [[ "$CONFIRM" =~ ^[nN]$ ]]; then
    warning "Benchmark annulé"
    exit 0
fi
echo ""

BENCHMARK_START=$(date +%s)
RESULTS_FILE="benchmark_results_$(date +%Y%m%d_%H%M%S).txt"

echo "═══════════════════════════════════════════════" | tee -a "$RESULTS_FILE"
echo "🎯 BENCHMARK IMAGEN - $(date)" | tee -a "$RESULTS_FILE"
echo "═══════════════════════════════════════════════" | tee -a "$RESULTS_FILE"
echo "" | tee -a "$RESULTS_FILE"

# Fonction pour attendre la génération
wait_for_generation() {
    local JOB_ID=$1
    local MAX_WAIT=600
    local ELAPSED=0

    while [ $ELAPSED -lt $MAX_WAIT ]; do
        STATUS_RESPONSE=$(curl -s --connect-timeout 5 "$API_URL/status/$JOB_ID" 2>/dev/null || echo "")

        if [ -z "$STATUS_RESPONSE" ]; then
            sleep 3
            ELAPSED=$((ELAPSED + 3))
            continue
        fi

        STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'UNKNOWN'))" 2>/dev/null)

        if [ "$STATUS" = "SUCCESS" ]; then
            FILENAME=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['filename'])")
            echo "$FILENAME"
            return 0
        elif [ "$STATUS" = "FAILURE" ]; then
            ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', 'Unknown'))")
            error "Génération échouée: $ERROR"
            echo "FAILED"
            return 1
        fi

        sleep 3
        ELAPSED=$((ELAPSED + 3))
    done

    error "Timeout"
    echo "TIMEOUT"
    return 1
}

# Boucle principale
for MODEL in "${MODELS[@]}"; do
    for LORA_CONFIG in "${LORA_CONFIGS[@]}"; do
        for STEPS in "${STEPS_CONFIGS[@]}"; do
            for GUIDANCE in "${GUIDANCE_CONFIGS[@]}"; do
                CURRENT=$((CURRENT + 1))

                # Construction du JSON
                if [ "$LORA_CONFIG" = "lora" ]; then
                    LORAS_JSON='[{"name": "civitai-618068", "weight": 0.8}]'
                    LORA_LABEL="lora"
                else
                    LORAS_JSON='[]'
                    LORA_LABEL="nolora"
                fi

                JSON_DATA="{
                  \"prompt\": \"$PROMPT\",
                  \"negative_prompt\": \"$NEGATIVE_PROMPT\",
                  \"model\": \"$MODEL\",
                  \"steps\": $STEPS,
                  \"guidance_scale\": $GUIDANCE,
                  \"loras\": $LORAS_JSON,
                  \"ip_strength\": 0.0
                }"

                LABEL="${MODEL}_${LORA_LABEL}_${STEPS}steps_g${GUIDANCE}"

                echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                echo -e "${CYAN}[$CURRENT/$TOTAL] $LABEL${NC}"
                echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

                # Soumission
                GEN_START=$(date +%s)
                RESPONSE=$(curl -s --connect-timeout 10 -X POST "$API_URL/generate" \
                  -H "Content-Type: application/json" \
                  -d "$JSON_DATA" 2>/dev/null)

                JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null)

                if [ -z "$JOB_ID" ]; then
                    error "Échec de soumission"
                    echo "$LABEL | FAILED (submit)" >> "$RESULTS_FILE"
                    continue
                fi

                info "Job: $JOB_ID - En attente..."

                # Attente
                FILENAME=$(wait_for_generation "$JOB_ID")
                GEN_END=$(date +%s)
                GEN_TIME=$((GEN_END - GEN_START))

                if [ "$FILENAME" = "FAILED" ] || [ "$FILENAME" = "TIMEOUT" ]; then
                    echo "$LABEL | $FILENAME" >> "$RESULTS_FILE"
                    warning "Échec: $FILENAME"
                else
                    success "Terminé: $FILENAME (${GEN_TIME}s)"
                    echo "$LABEL | $FILENAME | ${GEN_TIME}s" >> "$RESULTS_FILE"
                fi

                echo ""
                sleep 2  # Pause entre générations
            done
        done
    done
done

BENCHMARK_END=$(date +%s)
BENCHMARK_TIME=$((BENCHMARK_END - BENCHMARK_START))

echo "═══════════════════════════════════════════════" | tee -a "$RESULTS_FILE"
echo "✅ Benchmark terminé" | tee -a "$RESULTS_FILE"
echo "  Durée totale: $((BENCHMARK_TIME / 60))min $((BENCHMARK_TIME % 60))s" | tee -a "$RESULTS_FILE"
echo "  Résultats: $RESULTS_FILE" | tee -a "$RESULTS_FILE"
echo "═══════════════════════════════════════════════" | tee -a "$RESULTS_FILE"
echo ""

# Copier les images vers outputs local
info "Copie des images générées..."
mkdir -p /workspaces/imagen/outputs
docker run --rm -v electra-outputs:/src -v ${PWD}/outputs:/dest alpine sh -c "cp /src/*.png /dest/ 2>/dev/null || true"
success "Images copiées vers ./outputs/"
echo ""

echo "📁 Pour voir les résultats:"
echo "  - Fichiers: ./outputs/"
echo "  - Rapport: $RESULTS_FILE"
