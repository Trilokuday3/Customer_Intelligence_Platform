# FastAPI backend (src/api). Build from the repo root:
#   docker build -t customer-intelligence-api .
# Only the libraries the API needs to load and run the models are installed
# (.[api,serve]); training-only ones (shap, lightgbm, lifetimes) stay out so
# the image fits a 512 MB host. deploy/models/ holds the exact model files
# that produced the stored predictions. Local docker compose bind-mounts
# ./models over /app/models, so retraining there needs no rebuild.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
COPY deploy/models/ models/

RUN pip install --no-cache-dir -e ".[api,serve]"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Hosts such as Render assign the port through $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn api.main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
