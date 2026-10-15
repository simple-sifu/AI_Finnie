# Finnie local deployment (Story 10.3). Python 3.12 matches requirements.txt and docs/architecture.md §4.
FROM python:3.12-slim-bookworm

WORKDIR /app

# PyTorch/FAISS wheels are prebuilt; keep image lean with only runtime libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY config.yaml pyproject.toml ./
COPY src ./src
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "src/web_app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
