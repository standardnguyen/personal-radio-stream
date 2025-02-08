# media_downloader.py

import logging
import requests
import magic
from pathlib import Path
from typing import Optional
from media_types import MediaTypes
from media_validator import MediaValidator

class MediaDownloader:
    """Handles downloading and storing media files from Trello attachments"""
    
    def __init__(self, config, logger: logging.Logger):
        """
        Initialize the downloader with configuration
        
        Args:
            config: Configuration object containing API credentials and paths
            logger: Configured logger instance
        """
        self.config = config
        self.logger = logger
        self.validator = MediaValidator(logger)
        
        # Create an authenticated session for Trello API requests
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'OAuth oauth_consumer_key="{config.trello_api_key}", oauth_token="{config.trello_token}"'
        })
        
        # Ensure media directory exists
        self.config.media_dir.mkdir(exist_ok=True)
    
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
            file_path = self.config.media_dir / f"{safe_filename}{Path(attachment.name).suffix}"
            
            # Download file using authenticated session with progress tracking
            self.logger.info(f"Downloading attachment: {attachment.name}")
            response = self.session.get(attachment.url, stream=True)
            response.raise_for_status()
            
            file_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            # Save file in chunks to handle large files efficiently
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Log download progress for large files
                        if file_size > 10 * 1024 * 1024:  # 10MB
                            progress = (downloaded / file_size) * 100
                            if progress % 10 == 0:  # Log every 10%
                                self.logger.info(f"Download progress: {progress:.1f}%")
            
            # Validate the downloaded file's media type
            mime_type = magic.from_file(str(file_path), mime=True)
            if not MediaTypes.is_supported_format(mime_type):
                self.logger.error(f"Unsupported media type: {mime_type}")
                file_path.unlink()
                return None
            
            # Additional validation for audio files
            media_type = MediaTypes.get_media_type(mime_type)
            if media_type == 'audio':
                is_valid, error_message = self.validator.validate_audio_file(file_path, mime_type)
                if not is_valid:
                    self.logger.error(f"Audio validation failed: {error_message}")
                    file_path.unlink()
                    return None
            
            self.logger.info(f"Successfully downloaded and validated: {file_path}")
            return file_path
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error downloading attachment: {str(e)}")
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                self.logger.error("Authentication failed. Please verify your Trello API key and token.")
            return None
        except Exception as e:
            self.logger.error(f"Error downloading attachment: {str(e)}")
            return None
    
    def cleanup_media(self) -> None:
        """Remove old media files to maintain storage limits"""
        try:
            # Calculate current storage usage
            total_size = sum(f.stat().st_size for f in self.config.media_dir.glob('*'))
            
            if total_size > self.config.max_storage:
                self.logger.info("Cleaning up old media files...")
                files = sorted(
                    self.config.media_dir.glob('*'),
                    key=lambda x: x.stat().st_mtime
                )
                
                # Remove oldest files until we're under the limit
                for file in files:
                    if total_size <= self.config.max_storage:
                        break
                    
                    try:
                        file_size = file.stat().st_size
                        file.unlink()
                        total_size -= file_size
                        self.logger.info(f"Removed old file: {file}")
                    except Exception as e:
                        self.logger.error(f"Error removing file {file}: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error during media cleanup: {str(e)}")
