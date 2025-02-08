# media_manager.py

import time
import subprocess
import requests
import magic
from pathlib import Path
from typing import Optional, Tuple
from config_manager import StreamConfig
import logging

class MediaManager:
    """Handles media file operations and streaming"""
    
    # Define supported media formats
    SUPPORTED_FORMATS = {
        'video': ['video/mp4', 'video/mpeg', 'video/avi', 'video/x-matroska',
                 'video/webm', 'video/quicktime', 'video/x-flv'],
        'audio': ['audio/mpeg', 'audio/wav', 'audio/aac', 'audio/ogg',
                 'audio/flac', 'audio/x-m4a']
    }
    
    def __init__(self, config: StreamConfig, logger: logging.Logger):
        """
        Initialize the media manager
        
        Args:
            config: StreamConfig instance
            logger: Configured logger instance
        """
        self.config = config
        self.logger = logger
        self.current_process: Optional[subprocess.Popen] = None
    
    def download_attachment(self, attachment) -> Optional[Path]:
        """
        Download and validate a media attachment
        
        Args:
            attachment: Trello attachment object
            
        Returns:
            Path to downloaded file if successful, None otherwise
        """
        try:
            # Generate safe filename
            filename = Path(attachment.name).stem
            safe_filename = "".join(x for x in filename if x.isalnum() or x in "._- ")
            file_path = self.config.media_dir / safe_filename
            
            # Download file
            response = requests.get(attachment.url, stream=True)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Validate media type
            mime_type = magic.from_file(str(file_path), mime=True)
            if not self._is_supported_format(mime_type):
                self.logger.error(f"Unsupported media type: {mime_type}")
                file_path.unlink()
                return None
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"Error downloading attachment: {str(e)}")
            return None
    
    def _is_supported_format(self, mime_type: str) -> bool:
        """Check if the media format is supported"""
        return any(mime_type in formats 
                  for formats in self.SUPPORTED_FORMATS.values())
    
    def stream_media(self, media_path: Path, duration: Optional[int] = None) -> None:
        """
        Stream media file using FFmpeg
        
        Args:
            media_path: Path to the media file
            duration: Optional duration in seconds
        """
        try:
            # Build FFmpeg command
            command = [
                'ffmpeg',
                '-re',  # Read input at native framerate
                '-i', str(media_path),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-f', 'hls',
                '-hls_time', '10',
                '-hls_list_size', '6',
                '-hls_flags', 'delete_segments',
                str(self.config.hls_dir / 'playlist.m3u8')
            ]
            
            # Start streaming process
            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for completion or duration
            if duration:
                time.sleep(duration)
                self.stop_stream()
            else:
                self.current_process.wait()
                
        except Exception as e:
            self.logger.error(f"Error streaming media: {str(e)}")
            self.stop_stream()
    
    def stop_stream(self) -> None:
        """Stop the current stream if running"""
        if self.current_process:
            self.current_process.terminate()
            self.current_process = None
            
    def cleanup_media(self) -> None:
        """Remove old media files to maintain storage limits"""
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
