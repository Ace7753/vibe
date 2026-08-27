FROM python:3.12-slim-bookworm

# Install system dependencies + Node.js + Java
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    libgcc-s1 \
    libstdc++6 \
    gnupg \
    git \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the source files
COPY requirements.txt .
COPY app ./app
COPY vibe_icon_original.png .
COPY vibe-config.json .
COPY engines ./engines

# 1. Install ALL Python-based Downloaders from local source
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 \
    yt-dlp[default,curl-cffi] \
    ytmusicapi>=1.12.1 \
    zspotify && \
    pip install ./engines/votify && \
    pip install ./engines/savify && \
    pip install ./engines/onthespot

# 2. Install Node.js Downloaders from local source
RUN npm install -g ./engines/spotify-dl

# 3. Install Deno (required for modern YouTube decryption)
RUN spotdl --download-deno

# Create directories
RUN mkdir -p downloads archives

# Expose port
EXPOSE 8080

# Run with python -u to ensure logs are flushed immediately
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
