FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip libgl1-mesa-glx libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*

# Versions compatibles et récentes
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install numpy==1.26.4 && \
    pip3 install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install huggingface-hub==0.21.4 && \
    pip3 install diffusers==0.27.2 transformers==4.38.2 accelerate==0.27.2 safetensors==0.4.2 && \
    pip3 install compel==2.0.2 && \
    pip3 install fastapi==0.105.0 uvicorn==0.24.0 celery==5.3.4 redis==5.0.1 pillow==10.1.0 python-multipart==0.0.6

COPY app/ ./app/
COPY init_dirs.py ./

# Créer la structure de dossiers organisée
RUN python3 init_dirs.py

ENV PYTHONPATH=/app
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]