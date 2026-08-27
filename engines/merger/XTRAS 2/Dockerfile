FROM python:3.11-slim AS spotdl-builder

ARG SPOTDL_REPO=https://github.com/spotDL/spotify-downloader
ARG SPOTDL_REF=

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN if [ -n "$SPOTDL_REF" ]; then \
      git clone --depth 1 --branch "$SPOTDL_REF" "$SPOTDL_REPO" /spotdl-src; \
    else \
      git clone --depth 1 "$SPOTDL_REPO" /spotdl-src; \
    fi

WORKDIR /spotdl-src
RUN pip install --no-cache-dir --upgrade pip wheel \
    && pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOWNLOAD_DIR=/downloads \
    XDG_CONFIG_HOME=/config \
    XDG_CACHE_HOME=/config/.cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
COPY --from=spotdl-builder /wheels /wheels
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir /wheels/*.whl \
    && pip install --no-cache-dir yt-dlp \
    && rm -rf /wheels

COPY app ./app

RUN mkdir -p /downloads /config /config/.cache \
    && chmod 777 /downloads /config /config/.cache

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
