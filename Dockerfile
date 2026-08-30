FROM python:3.11-bookworm

# Install runtimes: Node, Java, Go, Build Tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl unzip libgcc-s1 libstdc++6 gnupg git build-essential \
    openjdk-17-jre-headless \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && curl -fsSL https://go.dev/dl/go1.23.0.linux-amd64.tar.gz -o go.tar.gz \
    && tar -C /usr/local -xzf go.tar.gz \
    && rm go.tar.gz \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/go/bin:${PATH}"

# Fix Protobuf and Path issues permanently
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
ENV PYTHONPATH="/app/engines/merger:/app/engines/merger/src:/app/engines/merger/savify:/app/engines/merger/votify:/app/engines/merger/antra:/app/antra_shared"

WORKDIR /app

# Copy ALL project files
COPY requirements.txt .
COPY app ./app
COPY vibe_icon_original.png .
COPY vibe-config.json .
COPY engines ./engines
COPY cookies.txt .

# 1. Install Global Requirements
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 "yt-dlp[default,curl-cffi]" ytmusicapi>=1.12.1 spotify-web-downloader

# 2. BRUTE-FORCE ENGINE MAPPING (Bypassing all path errors)
# Create direct shell-script launchers for every engine in /usr/local/bin
RUN cd /app/engines/merger && \
    echo '#!/bin/bash\nnode /app/engines/merger/cli.js "$@"' > /usr/local/bin/spotifydl && \
    echo '#!/bin/bash\nexport PYTHONPATH=$PYTHONPATH:/app/engines/merger/votify\npython3 -m votify "$@"' > /usr/local/bin/votify && \
    echo '#!/bin/bash\nexport PYTHONPATH=$PYTHONPATH:/app/engines/merger/src\npython3 /app/engines/merger/src/onthespot/cli.py "$@"' > /usr/local/bin/onthespot && \
    echo '#!/bin/bash\nexport PYTHONPATH=$PYTHONPATH:/app/engines/merger/savify\npython3 -m savify "$@"' > /usr/local/bin/savify && \
    echo '#!/bin/bash\nexport PYTHONPATH=$PYTHONPATH:/app/engines/merger/antra\npython3 -m antra "$@"' > /usr/local/bin/antra && \
    chmod +x /usr/local/bin/spotifydl /usr/local/bin/votify /usr/local/bin/onthespot /usr/local/bin/savify /usr/local/bin/antra

# 3. NPM Dependencies for Node Engines
RUN cd engines/merger && npm install || true

# 4. Decryption Master
RUN spotdl --download-deno

# Create folders
RUN mkdir -p downloads archives

EXPOSE 8080
CMD ["python", "-u", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
