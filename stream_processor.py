# stream_processor.py

from flask import Flask, send_from_directory
from threading import Thread
import time
from typing import Optional
import os  # Added for environment variable checks
from config_manager import StreamConfig, LoggerSetup
from trello_manager import TrelloManager
from media_manager import MediaManager

# Initialize Flask application for serving HLS streams
app = Flask(__name__)

class StreamQueueProcessor:
    """
    Main processor that coordinates Trello queue management and media streaming.
    Uses separate components for configuration, Trello operations, and media handling.
    Now includes HTTPS support for secure streaming.
    """
    
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
        """Initialize the stream processor with all required components"""
        # Create configuration
        self.config = StreamConfig(
            trello_api_key=trello_api_key,
            trello_token=trello_token,
            board_name=board_name,
            list_name=list_name,
            media_dir=media_dir,
            cleanup_interval_hours=cleanup_interval_hours,
            max_storage_mb=max_storage_mb,
            stream_port=stream_port,
            log_file=log_file
        )
        
        # Set up logging
        self.logger = LoggerSetup.setup_logger('StreamProcessor', log_file)
        
        # Initialize components
        self.trello = TrelloManager(self.config, self.logger)
        self.media = MediaManager(self.config, self.logger)
        
        # Set up Flask route
        self._setup_flask_routes()
        
        self.is_running = False
        self.last_cleanup = time.time()
    
    def _setup_flask_routes(self) -> None:
        """
        Configure Flask routes for HLS streaming with HTTPS support.
        Adds security headers for HTTPS enforcement when running on DigitalOcean.
        """
        @app.route('/stream/<path:filename>')
        def serve_hls(filename):
            # Serve the requested HLS stream file
            response = send_from_directory(
                str(self.config.hls_dir),
                filename
            )
            
            # Add security headers for HTTPS
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response

    def start(self) -> None:
        """
        Start the stream processor, including the Flask server and processing threads.
        This method initializes three daemon threads:
        1. Flask server for HLS streaming (now with HTTPS support)
        2. Queue processor for handling Trello cards
        3. Cleanup thread for managing storage
        """
        try:
            self.is_running = True
            
            # Start Flask server thread
            # DigitalOcean App Platform handles SSL termination, so we don't need
            # to configure SSL certificates directly in the application
            self.logger.info(f"Starting Flask server on port {self.config.stream_port}...")
            self.server_thread = Thread(
                target=lambda: app.run(
                    host='0.0.0.0',
                    port=self.config.stream_port,
                    debug=False,
                    use_reloader=False
                )
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Start queue processing thread
            self.logger.info("Starting queue processing thread...")
            self.process_thread = Thread(target=self._process_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            # Start cleanup thread
            self.logger.info("Starting cleanup thread...")
            self.cleanup_thread = Thread(target=self._cleanup_routine)
            self.cleanup_thread.daemon = True
            self.cleanup_thread.start()
            
        except Exception as e:
            self.logger.error(f"Error starting processor: {str(e)}")
            self.stop()
            raise

    def stop(self) -> None:
        """
        Stop the stream processor and clean up resources.
        This includes stopping the current stream and cleaning up HLS segments.
        """
        self.logger.info("Stopping stream processor...")
        self.is_running = False
        
        # Stop current stream
        self.media.stop_stream()
        
        # Clean up HLS segments
        self.logger.info("Cleaning up HLS segments...")
        for file in self.config.hls_dir.glob("*"):
            try:
                file.unlink()
            except Exception as e:
                self.logger.error(f"Error deleting {file}: {str(e)}")

    def _process_queue(self) -> None:
        """
        Main queue processing loop that continuously checks for new cards
        and processes them. This method runs in its own thread and handles
        the movement of cards through different Trello lists.
        """
        while self.is_running:
            try:
                # Get cards from Queue list
                queue_cards = self.trello.get_queue_cards()
                
                if queue_cards:
                    card = queue_cards[0]  # Get the first card
                    self.logger.info(f"Processing card: {card.name}")
                    
                    # Move card to Now Playing
                    self.trello.move_card_to_list(card, 'Now Playing')
                    
                    # Process the card
                    self._process_card(card)
                    
                    # Move card to Played list
                    self.trello.move_card_to_list(card, 'Played')
                
                # Check if cleanup is needed
                if time.time() - self.last_cleanup > self.config.cleanup_interval:
                    self._cleanup_routine()
                
                time.sleep(5)  # Prevent excessive API calls
                
            except Exception as e:
                self.logger.error(f"Error in queue processing: {str(e)}")
                time.sleep(30)  # Wait longer on error

    def _process_card(self, card) -> None:
        """
        Process a single card from the queue by downloading and streaming its media.
        
        Args:
            card: A Trello card object containing media attachments
        """
        try:
            # Get media attachment
            attachments = self.trello.get_card_attachments(card)
            if not attachments:
                self.logger.warning(f"No attachments found on card: {card.name}")
                return
            
            # Download and validate the first attachment
            attachment = attachments[0]
            media_path = self.media.download_attachment(attachment)
            
            if not media_path:
                self.logger.error(f"Failed to download attachment from card: {card.name}")
                return
            
            # Get duration from card description if available
            try:
                duration = int(card.description) if card.description.strip().isdigit() else None
            except (AttributeError, ValueError):
                duration = None
            
            # Stream the media
            self.media.stream_media(media_path, duration)
            
        except Exception as e:
            self.logger.error(f"Error processing card {card.name}: {str(e)}")

    def _cleanup_routine(self) -> None:
        """
        Periodic cleanup handler that manages storage and old files.
        This method is called automatically when the cleanup interval is reached.
        """
        try:
            self.logger.info("Starting cleanup routine...")
            self.media.cleanup_media()
            self.last_cleanup = time.time()
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")