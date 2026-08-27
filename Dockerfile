FROM python:3.11-bookworm

# Install ALL runtimes: Node, Java, Go, Build Tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl unzip libgcc-s1 libstdc++6 gnupg git build-essential \
    openjdk-17-jre-headless golang-go \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Fix Protobuf issue globally
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

# 2. Install EVERY Engine from Merger subfolders (The Arsenal)
# We go into each folder and install them one by one.
RUN if [ -d "engines/merger/votify" ]; then cd engines/merger/votify && pip install . ; fi
RUN if [ -d "engines/merger/savify" ]; then cd engines/merger/savify && pip install . ; fi
RUN if [ -d "engines/merger/antra" ]; then cd engines/merger/antra && pip install . ; fi
RUN if [ -f "engines/merger/setup.py" ]; then cd engines/merger && pip install . ; fi
RUN if [ -f "engines/merger/setup.cfg" ]; then cd engines/merger && pip install . ; fi

# 3. Install Node Engines (Linking them for global access)
RUN cd engines/merger && npm install && \
    ln -sf /app/engines/merger/cli.js /usr/local/bin/spotifydl && \
    chmod +x /app/engines/merger/cli.js

# 4. Decryption Master
RUN spotdl --download-deno

# Create folders
RUN mkdir -p downloads archives
RUN touch cookies.txt

EXPOSE 8080
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
