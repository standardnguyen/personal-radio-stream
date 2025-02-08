import os
import time
import subprocess
import requests
import magic
import logging
from pathlib import Path
from trello import TrelloClient
from threading import Thread
from typing import Optional, Tuple
from flask import Flask, send_from_directory

# Initialize Flask application for serving HLS streams
app = Flask(__name__)

class StreamQueueProcessor:
    """
    A processor that manages a queue of media files using Trello as a frontend.
    It downloads media from Trello cards, converts them to HLS format, and streams
    them in sequence while managing storage and cleanup.
    """
    
    # Define supported media formats for validation
    SUPPORTED_FORMATS = {
        'video': ['video/mp4', 'video/mpeg', 'video/avi', 'video/x-matroska', 
                 'video/webm', 'video/quicktime', 'video/x-flv'],
        'audio': ['audio/mpeg', 'audio/wav', 'audio/aac', 'audio/ogg', 
                 'audio/flac', 'audio/x-m4a']
    }

    def __init__(
        self,
        trello_api_key: str,
        trello_token: str,
        board_name: str,
        list_name: str,
        media_dir: str = "downloaded_media",
        cleanup_interval_hours: int = 24,
        max_storage_mb: int = 5000,
        stream_port: int = 8080,
        log_file: str = "stream_processor.log"
    ):
        """
        Initialize the StreamQueueProcessor with configuration parameters.
        """
        # Set up logging configuration with both file and console handlers
        self.logger = logging.getLogger('StreamProcessor')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(console_handler)

        # Log initialization parameters (safely)
        self.logger.info("Initializing StreamQueueProcessor")
        self.logger.info(f"Board Name: {board_name}")
        self.logger.info(f"List Name: {list_name}")
        self.logger.info(f"Media Directory: {media_dir}")
        self.logger.info(f"Stream Port: {stream_port}")
        self.logger.info(f"API Key Length: {len(trello_api_key) if trello_api_key else 'None'}")
        self.logger.info(f"Token Length: {len(trello_token) if trello_token else 'None'}")

        try:
            # Initialize Trello client
            self.logger.info("Creating Trello client...")
            self.client = TrelloClient(api_key=trello_api_key, token=trello_token)
            
            # Store configuration
            self.board_name = board_name
            self.list_name = list_name
            self._initialize_trello()

            # Configure storage settings
            self.media_dir = Path(media_dir)
            self.media_dir.mkdir(exist_ok=True)
            self.cleanup_interval = cleanup_interval_hours * 3600
            self.max_storage = max_storage_mb * 1024 * 1024
            self.last_cleanup = time.time()

            # Set up streaming configuration
            self.stream_port = stream_port
            self.hls_dir = Path("hls_segments")
            self.hls_dir.mkdir(exist_ok=True)
            self.current_process: Optional[subprocess.Popen] = None
            self.is_running = False

        except Exception as e:
            self.logger.error(f"Error during initialization: {str(e)}")
            raise

        # Configure Flask routes for HLS streaming
        @app.route('/stream/<path:filename>')
        def serve_hls(filename):
            return send_from_directory(str(self.hls_dir), filename)

    def _initialize_trello(self):
        """
        Initialize Trello board and create required lists if they don't exist.
        """
        try:
            # Test API connection first
            self.logger.info("Testing Trello API connection...")
            boards = list(self.client.list_boards())
            board_names = [board.name for board in boards]
            self.logger.info(f"Successfully connected to Trello. Found {len(boards)} boards:")
            self.logger.info(f"Available boards: {', '.join(board_names)}")
            
            # Find the specified board
            self.logger.info(f"Looking for board: '{self.board_name}'")
            matching_boards = [b for b in boards if b.name == self.board_name]
            
            if not matching_boards:
                error_msg = f"Board '{self.board_name}' not found. Available boards: {', '.join(board_names)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
                
            self.board = matching_boards[0]
            self.logger.info(f"Found board: {self.board.name} (ID: {self.board.id})")
            
            # Define and create required lists
            list_names = ['Queue', 'Now Playing', 'Played']
            self.lists = {}
            
            existing_lists = {lst.name: lst for lst in self.board.list_lists()}
            self.logger.info(f"Found existing lists: {', '.join(existing_lists.keys())}")
            
            for name in list_names:
                if name in existing_lists:
                    self.lists[name] = existing_lists[name]
                    self.logger.info(f"Using existing list: {name}")
                else:
                    self.lists[name] = self.board.add_list(name)
                    self.logger.info(f"Created new list: {name}")
            
            self.logger.info("Trello initialization completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Trello: {str(e)}")
            self.logger.error(f"Error type: {type(e).__name__}")
            if hasattr(e, 'response'):
                self.logger.error(f"Response status: {getattr(e.response, 'status_code', 'N/A')}")
                self.logger.error(f"Response text: {getattr(e.response, 'text', 'N/A')}")
            raise

    # Rest of the StreamQueueProcessor class remains the same...
    # [Previous methods for streaming, processing cards, etc. stay unchanged]