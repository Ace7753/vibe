FROM python:3.14-slim-bookworm

# Install system dependencies including Node.js (for spotify-dl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    libgcc-s1 \
    libstdc++6 \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y node-js \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python packages
# Forcing yt-dlp master branch for the absolute latest August 2026 bypasses
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 "https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz" ytmusicapi>=1.12.1 curl-cffi zspotify

# Install Node.js downloaders
RUN npm install -g spotify-dl

# Install Deno (required for modern YouTube decryption on cloud IPs)
RUN spotdl --download-deno

# Create directories
RUN mkdir -p downloads archives

# Copy app and assets
COPY app ./app
COPY vibe_icon_original.png .
COPY vibe-config.json .

# Diagnostic: List files
RUN ls -la /app

# Expose port
EXPOSE 8080

# Run with python -u to ensure logs are flushed immediately for AWS monitoring
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
