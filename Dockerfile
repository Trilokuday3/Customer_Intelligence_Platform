# FastAPI backend (src/api). Build from the repo root:
#   docker build -t customer-intelligence-api .
# Models are trained offline (scripts/build_backend_data.py) and mounted
# in, not baked into the image -- retraining shouldn't require a rebuild.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir -e ".[ml,api]"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
