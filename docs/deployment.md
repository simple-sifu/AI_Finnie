---
title: Finnie — Deployment Artifacts
story: 10.3
status: final
---

# Deployment (Story 10.3)

Everything an evaluator needs to run Finnie locally, without extra infrastructure (D-20, NFR12).

## Artifact checklist (PS §5)

| Artifact | Location | Story |
|---|---|---|
| Environment template | [`.env.example`](../.env.example) | 10.3 AC 1 |
| Pinned dependencies | [`requirements.txt`](../requirements.txt) | 10.3 AC 1 |
| Sample portfolios | [`src/data/samples/`](../src/data/samples/) | 2.4 / 10.3 AC 2 |
| Performance benchmarks | [`benchmarks.md`](benchmarks.md) | 9.4 / 10.3 AC 3 |
| Container image | [`Dockerfile`](../Dockerfile), [`docker-compose.yml`](../docker-compose.yml) | 10.3 AC 4 |
| Run-from-clone guide | [`README.md`](../README.md) § Development setup | 10.3 AC 5 |

The committed FAISS index under `src/data/index/` is included in the Docker image so RAG works without a rebuild.

## Option A — Python (recommended for development)

Follow [README § Development setup](../README.md#development-setup): clone, venv, `pip install -r requirements.txt`, `.env`, `streamlit run src/web_app/app.py`.

## Option B — Docker

**Prerequisites:** Docker Desktop (or Engine) and a filled `.env` file.

```bash
git clone https://github.com/simple-sifu/AI_Finnie.git
cd AI_Finnie
cp .env.example .env    # add OPENAI_API_KEY, ALPHA_VANTAGE_API_KEY, SERPAPI_API_KEY

docker compose up --build
```

Open http://localhost:8501

### Without Compose

```bash
docker build -t finnie:local .
docker run --rm -p 8501:8501 --env-file .env -v finnie-cache:/app/.cache finnie:local
```

**Notes**

- API keys are read from `.env` at container start; never bake secrets into the image.
- `.cache/` is mounted so market/news caches survive restarts within the volume.
- First chat may download the embedding model if not already cached in the volume (~90 MB).
- Image size is large because of PyTorch and sentence-transformers; build once on a stable network.

## Verify deployment

```bash
./scripts/final_check.sh           # config + pytest + UAT + benchmarks (Story 10.4)
```

Or step by step:

```bash
python -m src.core.config          # Configuration OK
pytest                             # full suite with coverage gate
pytest -k uat --cov-fail-under=0
python scripts/benchmark.py        # NFR13 offline benchmarks
```
