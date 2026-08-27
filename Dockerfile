FROM python:3.11-bookworm

# Install ALL runtimes: Node, Java, Go, Build Tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl unzip libgcc-s1 libstdc++6 gnupg git build-essential \
    openjdk-17-jre-headless golang-go \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy ALL project files
COPY requirements.txt .
COPY app ./app
COPY vibe_icon_original.png .
COPY vibe-config.json .
COPY engines ./engines

# 1. Install ALL Python Engines from Source (Forcing Python 3.11 Compatibility)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 \
    yt-dlp[default,curl-cffi] \
    ytmusicapi>=1.12.1 \
    zspotify && \
    pip install ./engines/votify && \
    pip install ./engines/savify && \
    pip install ./engines/onthespot

# 2. Install Node Engines
RUN npm install -g ./engines/spotify-dl && \
    npm install -g ./engines/ezytdl || true

# 3. Install Deno
RUN spotdl --download-deno

# Create folders
RUN mkdir -p downloads archives

EXPOSE 8080
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
