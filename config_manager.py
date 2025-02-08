# config_manager.py

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class StreamConfig:
    """Configuration settings for the stream processor"""
    trello_api_key: str
    trello_token: str
    board_name: str
    list_name: str
    media_dir: Path
    cleanup_interval_hours: int
    max_storage_mb: int
    stream_port: int
    log_file: str = "stream_processor.log"

    def __post_init__(self):
        """Validate and process configuration after initialization"""
        # Convert string paths to Path objects
        if isinstance(self.media_dir, str):
            self.media_dir = Path(self.media_dir)
        
        # Create necessary directories
        self.media_dir.mkdir(exist_ok=True)
        self.hls_dir = Path("hls_segments")
        self.hls_dir.mkdir(exist_ok=True)
        
        # Convert time and storage limits to base units
        self.cleanup_interval = self.cleanup_interval_hours * 3600
        self.max_storage = self.max_storage_mb * 1024 * 1024

class LoggerSetup:
    """Handles logging configuration for the application"""
    
    @staticmethod
    def setup_logger(name: str, log_file: str) -> logging.Logger:
        """
        Configure and return a logger with both file and console handlers
        
        Args:
            name: Name for the logger
            log_file: Path to the log file
            
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        # Create formatters and handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger