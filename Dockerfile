FROM python:3.12-slim
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
# non-root user can't write a numba jit cache next to site-packages; point it at /tmp instead
ENV NUMBA_CACHE_DIR=/tmp/numba_cache
# 모의투자 상태 파일(볼륨 마운트)을 non-root 유저가 쓸 수 있도록 미리 소유권을 넘긴다
RUN mkdir -p /app/data /app/archive && chown app:app /app/data /app/archive
USER app
ENTRYPOINT ["python", "-m", "app.backtest"]
