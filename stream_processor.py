# stream_processor.py

from threading import Thread
from typing import Optional
from pathlib import Path
import time
import sys
import logging

from config_manager import StreamConfig, LoggerSetup
from trello_manager import TrelloManager
from media_manager import MediaManager
from web_server import StreamServer
from player_template import PlayerTemplate
from simple_queue_processor import SimpleQueueProcessor  # Updated import

class StreamQueueProcessor:
    """
    Main processor that coordinates the streaming system components.
    Uses a simplified queue processing approach that just plays from the Queue list.
    """

    def __init__(
        self,
        trello_api_key: str,
        trello_token: str,
        board_name: str,
        list_name: str = "Queue",  # Default to just using Queue list
        media_dir: str = "downloaded_media",
        cleanup_interval_hours: int = 24,
        max_storage_mb: int = 5000,
        stream_port: int = 8080,
        log_file: str = "stream_processor.log"
    ):
        # Create configuration
        self.config = StreamConfig(
            trello_api_key=trello_api_key,
            trello_token=trello_token,
            board_name=board_name,
            list_name=list_name,  # We only need the Queue list now
            media_dir=media_dir,
            cleanup_interval_hours=cleanup_interval_hours,
            max_storage_mb=max_storage_mb,
            stream_port=stream_port,
            log_file=log_file
        )

        # Set up logging
        self.logger = LoggerSetup.setup_logger('StreamProcessor', log_file)

        try:
            self.logger.info("Initializing system components...")

            # Initialize core components
            self.trello = TrelloManager(self.config, self.logger)
            self.media = MediaManager(self.config, self.logger)
            self.server = StreamServer(self.config.hls_dir, self.logger)

            # Initialize simplified queue processor
            self.queue_processor = SimpleQueueProcessor(
                self.trello,
                self.media,
                self.config.cleanup_interval,
                self.logger
            )

            # Create player page
            PlayerTemplate.create_player_page(self.config.hls_dir, self.logger)

            # Initialize thread tracking
            self.server_thread: Optional[Thread] = None
            self.is_running = False

            self.logger.info("System components initialized successfully")

        except Exception as e:
            self.logger.error(f"Error during initialization: {str(e)}")
            raise

    def start(self) -> None:
        """Start all processor components"""
        try:
            self.is_running = True

            # Start web server
            self.logger.info(f"Starting web server on port {self.config.stream_port}...")
            self.server_thread = Thread(
                target=lambda: self.server.run(port=self.config.stream_port)
            )
            self.server_thread.daemon = True
            self.server_thread.start()

            # Start queue processor
            self.logger.info("Starting queue processor...")
            self.queue_processor.start()

            self.logger.info("All components started successfully")

        except Exception as e:
            self.logger.error(f"Error starting processor: {str(e)}")
            self.stop()
            raise

    def stop(self) -> None:
        """Stop all processor components"""
        self.logger.info("Stopping stream processor...")
        self.is_running = False

        try:
            # Stop queue processor
            if self.queue_processor:
                self.queue_processor.stop()

            # Stop current stream
            if self.media:
                self.media.stop_stream()

            # Clean up HLS segments
            self.logger.info("Cleaning up HLS segments...")
            for file in self.config.hls_dir.glob("*"):
                if file.is_file() and file.suffix in ['.ts', '.m3u8']:
                    try:
                        file.unlink()
                    except Exception as e:
                        self.logger.error(f"Error deleting {file}: {str(e)}")

            self.logger.info("Stream processor stopped successfully")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
            raise

    def get_stream_url(self) -> str:
        """Get the URL for accessing the HLS stream"""
        return f"http://localhost:{self.config.stream_port}/stream/playlist.m3u8"

    def get_player_url(self) -> str:
        """Get the URL for accessing the web player"""
        return f"http://localhost:{self.config.stream_port}/"

    def display_usage_info(self) -> None:
        """Display simplified usage information"""
        self.logger.info("\nStream Processor Usage Information:")
        self.logger.info("1. Add a card to the 'Queue' list in your Trello board")
        self.logger.info("2. Attach a media file to the card")
        self.logger.info("3. (Optional) Add duration in seconds in the card description")
        self.logger.info("\nCards will play in order and be archived when complete")
        self.logger.info("\nAccess Points:")
        self.logger.info(f"- Web Player: {self.get_player_url()}")
        self.logger.info(f"- HLS Stream: {self.get_stream_url()}")
        self.logger.info("\nSupported Media Types:")
        self.logger.info("- Video: MP4, MPEG, AVI, MKV, WebM, MOV, FLV")
        self.logger.info("- Audio: MP3, WAV, AAC, OGG, FLAC, M4A")
