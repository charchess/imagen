#!/bin/bash
# Génération: Panther Cyborg avec PonyXL + LoRA Civitai 618068

set -e

echo "🎨 Génération: Panther Cyborg"
echo "=============================="

# Créer la requête
JOB_RESPONSE=$(curl -s -X POST http://localhost:8009/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Masterpiece, high-fidelity digital painting, cinematic lighting, volumetric atmosphere, rim lighting, carbon fiber texture, glowing blue circuits, 8k resolution, professional illustration style, vibrant colors, sharp focus, solid white background. Character: A stunning anthropomorphic panther cyborg. Sleek black carbon skin, electric blue neon lines, azure eyes. Alluring feminine silhouette. Form-fitting futuristic bodysuit. Expression: Finger to lips, intense concentration, holographic blueprints reflected in her azure eyes, analytical pose.",
    "negative_prompt": "low quality, blurry, distorted, bad anatomy, worst quality, low res, ugly, watermark, signature, text",
    "model": "pony-xl-v6",
    "loras": [
      {
        "name": "civitai-618068",
        "weight": 0.8
      }
    ],
    "steps": 40,
    "guidance_scale": 7.5,
    "seed": 42
  }')

# Extraire le job_id
JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.job_id')

if [ "$JOB_ID" = "null" ] || [ -z "$JOB_ID" ]; then
    echo "❌ Erreur lors de la création du job:"
    echo "$JOB_RESPONSE" | jq '.'
    exit 1
fi

echo "✅ Job créé: $JOB_ID"
echo ""
echo "⏳ Génération en cours..."
echo "   (PonyXL sera téléchargé au premier usage: ~6.5GB, peut prendre 10-15 min)"
echo "   (Génération: ~5-7 min avec 40 steps)"
echo ""

# Polling du statut
RETRY_COUNT=0
MAX_RETRIES=200  # 200 * 5s = 16 minutes max

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    STATUS_RESPONSE=$(curl -s http://localhost:8009/status/$JOB_ID)
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')

    case "$STATUS" in
        "SUCCESS")
            echo ""
            echo "✅ Génération terminée!"

            # Afficher les métadonnées
            echo ""
            echo "📊 Métadonnées:"
            echo "$STATUS_RESPONSE" | jq '.result.metadata'

            # Télécharger l'image
            FILENAME=$(echo "$STATUS_RESPONSE" | jq -r '.result.filename')
            echo ""
            echo "⬇️  Téléchargement de l'image..."
            curl -s http://localhost:8009/image/$JOB_ID -o "./$FILENAME"

            echo "✅ Image sauvegardée: ./$FILENAME"
            echo ""
            echo "🎉 C'est prêt! Ouvre l'image pour voir le résultat."
            exit 0
            ;;

        "FAILURE")
            echo ""
            echo "❌ Génération échouée:"
            echo "$STATUS_RESPONSE" | jq '.'
            exit 1
            ;;

        "PROGRESS")
            META=$(echo "$STATUS_RESPONSE" | jq -r '.meta.step // "en cours"')
            PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.meta.progress // 0')
            echo -ne "\r⏳ Status: $STATUS - $META ($PROGRESS%)    "
            ;;

        *)
            echo -ne "\r⏳ Status: $STATUS    "
            ;;
    esac

    sleep 5
    ((RETRY_COUNT++))
done

echo ""
echo "❌ Timeout: La génération prend trop de temps"
echo "   Vérifier les logs: docker-compose logs worker"
exit 1
