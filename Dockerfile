FROM python:3.14-slim-bookworm

# Install system dependencies + Node.js + Java (for SpotiFlyer cores)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    libgcc-s1 \
    libstdc++6 \
    gnupg \
    openjdk-17-jre-headless \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# 1. Install ALL Python-based Downloaders from GitHub/PyPI
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 \
    "https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz" \
    ytmusicapi>=1.12.1 \
    curl-cffi \
    zspotify \
    votify \
    savify \
    onthespot \
    spotify-web-downloader \
    YoutubeSpotifyDL

# 2. Install ALL Node.js-based Downloaders
RUN npm install -g spotify-dl smd spotify-playlist-downloader

# 3. Install Deno (required for modern YouTube decryption)
RUN spotdl --download-deno

# Create directories
RUN mkdir -p downloads archives

# Copy app and assets
COPY app ./app
COPY vibe_icon_original.png .
COPY vibe-config.json .

# Expose port
EXPOSE 8080

# Run with python -u to ensure logs are flushed immediately
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
