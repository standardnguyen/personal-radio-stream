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

# Add executable permissions to entrypoint script
RUN chmod +x docker-entrypoint.sh

# Create media and HLS directories
RUN mkdir -p downloaded_media hls_segments

# Instead of creating a new user, adjust file permissions
# This ensures the directories are accessible but avoids user creation complexity
RUN chmod -R 755 /app /downloaded_media /hls_segments

# Optional: If you still want to run as a non-root user
# Uncomment the following lines if the previous approach fails
# RUN useradd -m -s /bin/bash streamuser
# RUN chown -R streamuser:streamuser /app /downloaded_media /hls_segments
# USER streamuser

# Use the entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "start_stream.py"]