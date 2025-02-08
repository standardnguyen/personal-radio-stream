import time
import subprocess
import requests
import magic
from pathlib import Path
from typing import Optional
from config_manager import StreamConfig
import logging

class MediaManager:
    """
    Handles all media-related operations including downloading, format validation,
    and streaming of media files from Trello attachments.
    """
    
    # Define supported media formats with their MIME types
    SUPPORTED_FORMATS = {
        'video': ['video/mp4', 'video/mpeg', 'video/avi', 'video/x-matroska',
                 'video/webm', 'video/quicktime', 'video/x-flv'],
        'audio': ['audio/mpeg', 'audio/wav', 'audio/aac', 'audio/ogg',
                 'audio/flac', 'audio/x-m4a']
    }
    
    def __init__(self, config: StreamConfig, logger: logging.Logger):
        """
        Initialize the media manager with configuration and logging
        
        Args:
            config: StreamConfig instance containing all necessary settings
            logger: Configured logger instance for error and info logging
        """
        self.config = config
        self.logger = logger
        self.current_process: Optional[subprocess.Popen] = None
        
        # Create an authenticated session for Trello API requests
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'OAuth oauth_consumer_key="{config.trello_api_key}", oauth_token="{config.trello_token}"'
        })
    
    def _is_supported_format(self, mime_type: str) -> bool:
        """
        Check if a given MIME type is in our supported formats list
        
        Args:
            mime_type: The MIME type string to check (e.g., 'audio/mp3')
            
        Returns:
            bool: True if the format is supported, False otherwise
        """
        # Check if the MIME type exists in any of our format categories
        return any(mime_type in formats 
                  for formats in self.SUPPORTED_FORMATS.values())
    
    def download_attachment(self, attachment) -> Optional[Path]:
        """
        Download and validate a media attachment from Trello
        
        Args:
            attachment: Trello attachment object containing url and name
            
        Returns:
            Path: Path to the downloaded file if successful
            None: If download or validation fails
        """
        try:
            # Generate safe filename from attachment name
            filename = Path(attachment.name).stem
            safe_filename = "".join(x for x in filename if x.isalnum() or x in "._- ")
            file_path = self.config.media_dir / safe_filename
            
            # Download file using authenticated session
            self.logger.info(f"Downloading attachment: {attachment.name}")
            response = self.session.get(attachment.url, stream=True)
            response.raise_for_status()
            
            # Save file in chunks to handle large files efficiently
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Validate the downloaded file's media type
            mime_type = magic.from_file(str(file_path), mime=True)
            if not self._is_supported_format(mime_type):
                self.logger.error(f"Unsupported media type: {mime_type}")
                file_path.unlink()  # Delete invalid file
                return None
            
            self.logger.info(f"Successfully downloaded and validated: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"Error downloading attachment: {str(e)}")
            if 'response' in locals() and response.status_code == 401:
                self.logger.error("Authentication failed. Please verify your Trello API key and token.")
            return None
    
    def stream_media(self, media_path: Path, duration: Optional[int] = None) -> None:
        """
        Stream media file using FFmpeg with HLS format
        
        Args:
            media_path: Path to the media file to stream
            duration: Optional duration in seconds to stream
        """
        try:
            # Build FFmpeg command for HLS streaming
            command = [
                'ffmpeg',
                '-re',  # Read input at native framerate
                '-i', str(media_path),
                '-c:v', 'libx264',  # Video codec
                '-c:a', 'aac',      # Audio codec
                '-f', 'hls',        # HLS format
                '-hls_time', '10',  # Segment duration
                '-hls_list_size', '6',
                '-hls_flags', 'delete_segments',
                str(self.config.hls_dir / 'playlist.m3u8')
            ]
            
            # Start streaming process
            self.logger.info(f"Starting stream for: {media_path}")
            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Handle stream duration
            if duration:
                time.sleep(duration)
                self.stop_stream()
            else:
                self.current_process.wait()
                
        except Exception as e:
            self.logger.error(f"Error streaming media: {str(e)}")
            self.stop_stream()
    
    def stop_stream(self) -> None:
        """Stop the current stream if one is running"""
        if self.current_process:
            self.current_process.terminate()
            self.current_process = None
            self.logger.info("Stream stopped")
            
    def cleanup_media(self) -> None:
        """
        Remove old media files to maintain storage limits.
        Deletes oldest files first when storage limit is exceeded.
        """
        try:
            total_size = 0
            files = []
            
            # Calculate total size and gather file info
            for file in self.config.media_dir.glob("*"):
                if file.is_file():
                    size = file.stat().st_size
                    files.append((file, size))
                    total_size += size
            
            # Sort files by modification time (oldest first)
            files.sort(key=lambda x: x[0].stat().st_mtime)
            
            # Remove oldest files until under storage limit
            while total_size > self.config.max_storage and files:
                file, size = files.pop(0)
                try:
                    file.unlink()
                    total_size -= size
                    self.logger.info(f"Cleaned up: {file.name}")
                except Exception as e:
                    self.logger.error(f"Error deleting {file}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")