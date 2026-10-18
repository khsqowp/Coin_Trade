FROM python:3.12-slim

ARG KRONOS_GIT_REF=67b630e67f6a18c9e9be918d9b4337c960db1e9a
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/Kronos \
    && cd /opt/Kronos \
    && git init -q \
    && git remote add origin https://github.com/shiyu-coder/Kronos.git \
    && git fetch --depth 1 origin "${KRONOS_GIT_REF}" \
    && git checkout -q FETCH_HEAD

WORKDIR /app
COPY shadow_predictor/requirements.txt ./requirements-shadow.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple -r requirements-shadow.txt \
    && groupadd --system app && useradd --system --gid app app \
    && mkdir -p /output /models && chown -R app:app /output /models

ENV PYTHONPATH=/opt/Kronos:/app
RUN python -c "from model import Kronos, KronosTokenizer; KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-2k'); Kronos.from_pretrained('NeoQuasar/Kronos-mini')" \
    && chown -R app:app /models
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
COPY shadow_predictor/core.py shadow_predictor/main.py ./
USER app
ENTRYPOINT ["python", "-u", "main.py"]
