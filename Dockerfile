FROM python:3.14-slim-bookworm

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    libgcc-s1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
# spotdl v4.5.2 is the required hotfix for July/August 2026
# Adding curl-cffi for yt-dlp impersonation support (Stealth Mode)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir spotdl==4.5.2 "yt-dlp[default,curl-cffi]" ytmusicapi>=1.12.1

# Install Deno (required for modern YouTube decryption on cloud IPs)
RUN spotdl --download-deno

# Create directories
RUN mkdir -p downloads archives

# Copy app and cookies
COPY app ./app
COPY cookies.txt .
RUN chmod 644 cookies.txt

# Diagnostic: List files to ensure cookies.txt is present
RUN ls -la /app

# Expose port
EXPOSE 8080

# Run
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
