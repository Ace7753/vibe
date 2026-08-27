FROM python:3.11-bookworm

# Install ALL runtimes: Node, Java, Go, Build Tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl unzip libgcc-s1 libstdc++6 gnupg git build-essential \
    openjdk-17-jre-headless golang-go \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Fix Protobuf issue globally for all engines
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

WORKDIR /app

# Copy ALL project files
COPY requirements.txt .
COPY app ./app
COPY vibe_icon_original.png .
COPY vibe-config.json .
COPY engines ./engines

# 1. Install Primary Engines
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 "yt-dlp[default,curl-cffi]" ytmusicapi>=1.12.1

# 2. Install Every Engine from Local Source (One by One for maximum stability)
# We use -e or direct path to ensure binaries are linked to /usr/local/bin
RUN pip install ./engines/votify || echo "Votify failed"
RUN pip install ./engines/onthespot || echo "OnTheSpot failed"
RUN pip install ./engines/savify || echo "Savify failed"

# 3. Install Node Engines (Using full path linking)
RUN npm install -g ./engines/spotify-dl && \
    ln -sf /usr/local/lib/node_modules/@swapnilsoni1999/spotify-dl/cli.js /usr/local/bin/spotifydl || true

# 4. Decryption Master
RUN spotdl --download-deno

# Create folders
RUN mkdir -p downloads archives

EXPOSE 8080
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
