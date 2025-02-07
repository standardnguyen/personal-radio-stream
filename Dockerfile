# Start with Python base image
FROM python:3.9-slim

# Install VLC and other dependencies
RUN apt-get update && apt-get install -y \
    vlc \
    libmagic1 \
    gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create media directory
RUN mkdir -p downloaded_media

# Create a non-root user for running VLC
RUN useradd -m vlcuser && \
    chown -R vlcuser:vlcuser /app

# Create an entrypoint script to handle configuration
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER vlcuser

# Use the entrypoint script
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "start_stream.py"]
