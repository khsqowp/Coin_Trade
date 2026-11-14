FROM python:3.12-slim
RUN pip install --no-cache-dir ccxt pandas numpy pyarrow requests jsonschema pytest
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 HOME=/tmp PYTHONUNBUFFERED=1
WORKDIR /app
USER 10001:10001
ENTRYPOINT ["python","-m","tp.cli"]
