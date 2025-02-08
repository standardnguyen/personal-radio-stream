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
        
        Args:
            trello_api_key: API key for Trello authentication
            trello_token: Token for Trello authentication
            board_name: Name of the Trello board to use
            list_name: Name of the list to monitor for new cards
            media_dir: Directory to store downloaded media files
            cleanup_interval_hours: How often to run storage cleanup
            max_storage_mb: Maximum storage space to use in megabytes
            stream_port: Port number for the HLS stream server
            log_file: Path to the log file
        """
        # Set up logging configuration
        self.logger = logging.getLogger('StreamProcessor')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

        # Initialize Trello client and board configuration
        self.client = TrelloClient(api_key=trello_api_key, token=trello_token)
        self.board_name = board_name
        self.list_name = list_name
        self._initialize_trello()

        # Configure storage settings
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(exist_ok=True)
        self.cleanup_interval = cleanup_interval_hours * 3600  # Convert hours to seconds
        self.max_storage = max_storage_mb * 1024 * 1024  # Convert MB to bytes
        self.last_cleanup = time.time()

        # Set up streaming configuration
        self.stream_port = stream_port
        self.hls_dir = Path("hls_segments")
        self.hls_dir.mkdir(exist_ok=True)
        self.current_process: Optional[subprocess.Popen] = None
        self.is_running = False

        # Configure Flask routes for HLS streaming
        @app.route('/stream/<path:filename>')
        def serve_hls(filename):
            return send_from_directory(str(self.hls_dir), filename)

    def _initialize_trello(self):
        """
        Initialize Trello board and create required lists if they don't exist.
        Raises ValueError if the specified board cannot be found.
        """
        try:
            # Find the specified board
            self.board = next(board for board in self.client.list_boards() 
                            if board.name == self.board_name)
            
            # Define and create required lists
            list_names = ['Queue', 'Now Playing', 'Played']
            self.lists = {}
            
            existing_lists = {lst.name: lst for lst in self.board.list_lists()}
            
            for name in list_names:
                if name in existing_lists:
                    self.lists[name] = existing_lists[name]
                else:
                    self.lists[name] = self.board.add_list(name)
            
            self.logger.info(f"Initialized Trello board: {self.board_name}")
            
        except StopIteration:
            raise ValueError(f"Board '{self.board_name}' not found")
        except Exception as e:
            self.logger.error(f"Failed to initialize Trello: {str(e)}")
            raise

    def start_hls_stream(self, input_path: str):
        """
        Start an HLS stream from the given input file.
        
        Args:
            input_path: Path to the input media file
        """
        # Clear any existing HLS segments
        for file in self.hls_dir.glob('*'):
            file.unlink()
            
        # Configure FFmpeg command for HLS streaming
        command = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-f', 'hls',
            '-hls_time', '10',  # Segment duration in seconds
            '-hls_list_size', '6',  # Number of segments to keep
            '-hls_flags', 'delete_segments',
            f'{self.hls_dir}/playlist.m3u8'
        ]
        
        # Start FFmpeg process
        self.current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def _process_card(self, card):
        """
        Process a single card from the queue, including downloading and streaming
        its attached media file.
        
        Args:
            card: Trello card object to process
        """
        try:
            # Move card to Now Playing list
            card.change_list(self.lists['Now Playing'].id)
            
            # Get attachments from the card
            attachments = card.get_attachments()
            if not attachments:
                self.logger.warning(f"No attachments found for card: {card.name}")
                card.change_list(self.lists['Played'].id)
                return
            
            # Download and process the first attachment
            attachment = attachments[0]
            media_path = self._download_attachment(attachment)
            
            if not media_path:
                self.logger.error(f"Failed to download attachment for card: {card.name}")
                card.change_list(self.lists['Played'].id)
                return
            
            # Start streaming the media file
            self.start_hls_stream(str(media_path))
            
            # Get duration from card description or use default
            try:
                duration = int(card.description.strip() or "300")
            except ValueError:
                duration = 300
            
            # Wait for the specified duration
            time.sleep(duration)
            
            # Clean up streaming process
            if self.current_process:
                self.current_process.terminate()
            
            # Move card to Played list
            card.change_list(self.lists['Played'].id)
            
        except Exception as e:
            self.logger.error(f"Error processing card {card.name}: {str(e)}")
            try:
                card.change_list(self.lists['Played'].id)
            except:
                pass

    def _download_attachment(self, attachment) -> Optional[Path]:
        """
        Download an attachment from Trello and save it locally.
        
        Args:
            attachment: Trello attachment object
            
        Returns:
            Path to downloaded file or None if download failed
        """
        try:
            response = requests.get(attachment.url, stream=True)
            response.raise_for_status()
            
            file_path = self.media_dir / attachment.file_name
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"Failed to download attachment: {str(e)}")
            return None

    def _cleanup_storage(self):
        """
        Clean up old media files if storage limit is exceeded.
        Removes oldest files first until under the storage limit.
        """
        try:
            total_size = sum(f.stat().st_size for f in self.media_dir.glob('*'))
            
            if total_size > self.max_storage:
                # Sort files by modification time (oldest first)
                files = sorted(self.media_dir.glob('*'), 
                             key=lambda x: x.stat().st_mtime)
                
                # Remove files until under storage limit
                for file in files:
                    if total_size <= self.max_storage:
                        break
                    
                    size = file.stat().st_size
                    file.unlink()
                    total_size -= size
            
            self.last_cleanup = time.time()
            
        except Exception as e:
            self.logger.error(f"Error during storage cleanup: {str(e)}")

    def check_file_type(self, file_path: str) -> Tuple[bool, str]:
        """
        Check if a file's type is supported by the processor.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            Tuple of (is_supported, mime_type)
        """
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        
        supported = any(
            file_type in formats 
            for formats in self.SUPPORTED_FORMATS.values()
        )
        
        return supported, file_type

    def process_queue(self):
        """
        Main processing loop that monitors the queue and processes cards.
        Runs continuously while is_running is True.
        """
        while self.is_running:
            try:
                # Check if cleanup is needed
                if time.time() - self.last_cleanup >= self.cleanup_interval:
                    self._cleanup_storage()
                
                # Get next card from queue
                cards = self.lists['Queue'].list_cards()
                if not cards:
                    time.sleep(5)  # Wait if queue is empty
                    continue
                
                # Process the first card in queue
                card = cards[0]
                self._process_card(card)
                
            except Exception as e:
                self.logger.error(f"Error in queue processing: {str(e)}")
                time.sleep(5)  # Wait before retrying

    def start(self):
        """
        Start the queue processor and web server in separate threads.
        """
        self.is_running = True
        
        # Start queue processing thread
        self.process_thread = Thread(target=self.process_queue)
        self.process_thread.start()
        
        # Start Flask server thread
        self.web_thread = Thread(target=lambda: app.run(
            host='0.0.0.0',
            port=self.stream_port,
            threaded=True
        ))
        self.web_thread.start()
        
        self.logger.info("Queue processor and web server started")
        print("Queue processor and web server started")

    def stop(self):
        """
        Stop the queue processor and web server gracefully.
        """
        self.is_running = False
        if self.current_process:
            self.current_process.terminate()
        self.process_thread.join()
        # Flask shutdown handled by the platform
        self.logger.info("Queue processor stopped")
        print("Queue processor stopped")