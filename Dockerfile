# ---------- stage 1: build the React app ----------
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build      # -> /web/dist

# ---------- stage 2: python runtime ----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/hf \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# libgomp1 is required by LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

# app source (api.py, agent/, models/, proj/, utils/, ...) + built frontend
COPY . .
COPY --from=web /web/dist ./web/dist

# bake the demo data + FAISS index (downloads MiniLM into HF_HOME, cached in image)
RUN python models/prepare_demo.py

# open perms so it works whether HF runs as root or uid 1000, and the SQLite db is writable
RUN chmod -R a+rwX /app

EXPOSE 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
