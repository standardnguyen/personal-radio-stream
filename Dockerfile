# Start with Python base image
FROM python:3.9-slim

# Install FFmpeg and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt flask

# Copy application code
COPY . .

# Create media and HLS directories
RUN mkdir -p downloaded_media hls_segments

# Create a non-root user
RUN useradd -m streamuser && \
    chown -R streamuser:streamuser /app

# Switch to non-root user
USER streamuser

# Use the entrypoint script
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "start_stream.py"]