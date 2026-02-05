from diffusers import StableDiffusionXLPipeline, AutoencoderKL
from transformers import CLIPVisionModelWithProjection
import torch

print("⬇️ Téléchargement SDXL Base...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True,
    cache_dir="./models"
)

print("⬇️ Téléchargement VAE Fix...")
vae = AutoencoderKL.from_pretrained(
    "madebyollin/sdxl-vae-fp16-fix",
    torch_dtype=torch.float16,
    cache_dir="./models"
)

print("⬇️ Téléchargement IP-Adapter...")
# Le téléchargement se fera automatiquement au premier chargement, 
# mais on peut forcer le preload ici si besoin
import urllib.request
import os

ip_adapter_base = "./models/IP-Adapter"

files = [
    ("https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter_sdxl.bin", 
     "sdxl_models/ip-adapter_sdxl.bin"),
    ("https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/config.json", 
     "models/image_encoder/config.json"),
    ("https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors", 
     "models/image_encoder/model.safetensors"),
]

for url, rel_path in files:
    filepath = os.path.join(ip_adapter_base, rel_path)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        print(f"Downloading {rel_path}...")
        urllib.request.urlretrieve(url, filepath)

print("✅ Modèles prêts!")