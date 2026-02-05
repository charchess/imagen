#!/bin/bash
# Script pour récupérer les images générées depuis le volume Docker

OUTPUT_DIR="${1:-./outputs_local}"

echo "📥 Récupération des images générées..."
echo ""

# Créer le dossier de sortie
mkdir -p "$OUTPUT_DIR"

# Copier tous les fichiers depuis le volume
docker cp imagen-worker-1:/app/outputs/. "$OUTPUT_DIR/"

echo "✅ Images récupérées dans: $OUTPUT_DIR"
echo ""
echo "📊 Contenu:"
ls -lh "$OUTPUT_DIR"/*.png 2>/dev/null || echo "  Aucune image PNG trouvée"
echo ""
echo "Total des fichiers:"
ls -1 "$OUTPUT_DIR" | wc -l
