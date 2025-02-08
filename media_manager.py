# media_manager.py

import logging
from pathlib import Path
from typing import Optional
from media_downloader import MediaDownloader
from media_streamer import MediaStreamer
from media_validator import MediaValidator

class MediaManager:
    """
    Coordinates all media-related operations including downloading, validation,
    and streaming of media files from Trello attachments.
    
    This class serves as a facade for the various media handling components,
    providing a simplified interface for the stream processor to use.
    """
    
    def __init__(self, config, logger: logging.Logger):
        """
        Initialize the media manager with all required components
        
        Args:
            config: Configuration object containing all necessary settings
            logger: Configured logger instance for error and info logging
        """
        self.config = config
        self.logger = logger
        
        # Initialize components
        self.downloader = MediaDownloader(config, logger)
        self.streamer = MediaStreamer(config, logger)
        self.validator = MediaValidator(logger)
    
    def download_attachment(self, attachment) -> Optional[Path]:
        """
        Download and validate a media attachment from Trello
        
        Args:
            attachment: Trello attachment object containing url and name
            
        Returns:
            Path: Path to the downloaded file if successful
            None: If download or validation fails
        """
        return self.downloader.download_attachment(attachment)
    
    def stream_media(self, media_path: Path, duration: Optional[int] = None, wait_for_completion: bool = True) -> None:
        """
        Stream media file using FFmpeg with optimized HLS settings
        
        Args:
            media_path: Path to the media file to stream
            duration: Optional duration in seconds to stream
            wait_for_completion: Whether to wait for the current file to finish
        """
        self.streamer.stream_media(media_path, duration, wait_for_completion)
    
    def stop_stream(self) -> None:
        """Stop the current stream if one is running"""
        self.streamer.stop_stream()
    
    def cleanup_media(self) -> None:
        """Remove old media files to maintain storage limits"""
        self.downloader.cleanup_media()
    
    @property
    def current_media(self) -> Optional[Path]:
        """Get the path of the currently streaming media file"""
        return self.streamer.current_media