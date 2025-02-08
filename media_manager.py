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
        
        # Create session with Trello auth headers
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'OAuth oauth_consumer_key="{config.trello_api_key}", oauth_token="{config.trello_token}"'
        })
    
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
            
            # Download file using authenticated session
            response = self.session.get(attachment.url, stream=True)
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
            if 'response' in locals() and response.status_code == 401:
                self.logger.error("Authentication failed. Please verify your Trello API key and token.")
            return None