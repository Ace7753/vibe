FROM python:3.12-slim-bookworm

# Install system dependencies + Node.js
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

# Copy requirements
COPY requirements.txt .

# 1. Install Top-Tier Python Downloaders (Confirmed August 2026 Stable)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 \
    yt-dlp[default,curl-cffi] \
    ytmusicapi>=1.12.1 \
    zspotify \
    spotify-web-downloader

# 2. Install Top-Tier Node.js Downloaders
RUN npm install -g spotify-dl

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
