# stream_processor.py

from flask import Flask, send_from_directory
from threading import Thread
import time
from typing import Optional
import os
from config_manager import StreamConfig, LoggerSetup
from trello_manager import TrelloManager
from media_manager import MediaManager

# Initialize Flask application for serving HLS streams
app = Flask(__name__)

class StreamQueueProcessor:
    """
    Main processor that coordinates Trello queue management and media streaming.
    This class serves as the central hub that:
    1. Manages the web server for HLS streaming
    2. Processes the Trello queue
    3. Handles media file downloading and streaming
    4. Maintains continuous playback between tracks
    """
    
    # HTML template for the web player with HLS.js for broader browser support
    PLAYER_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Player</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.4.12/hls.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: system-ui, -apple-system, sans-serif;
            background: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .player-wrapper {
            width: 100%;
            margin: 20px 0;
        }
        #videoPlayer {
            width: 100%;
            background: #000;
            border-radius: 4px;
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            background: #e8f5e9;
            color: #2e7d32;
        }
        .error {
            background: #ffebee;
            color: #c62828;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Stream Player</h1>
        <div class="player-wrapper">
            <video id="videoPlayer" controls></video>
        </div>
        <div id="status" class="status">Connecting to stream...</div>
    </div>

    <script>
        const video = document.getElementById('videoPlayer');
        const status = document.getElementById('status');
        const streamUrl = '/stream/playlist.m3u8';

        function initPlayer() {
            if (Hls.isSupported()) {
                const hls = new Hls({
                    debug: false,
                    enableWorker: true,
                    lowLatencyMode: true,
                    backBufferLength: 90
                });
                
                hls.loadSource(streamUrl);
                hls.attachMedia(video);
                
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    status.textContent = 'Stream ready - Playing...';
                    video.play().catch(e => {
                        status.textContent = 'Click play to start streaming';
                    });
                });

                hls.on(Hls.Events.ERROR, (event, data) => {
                    if (data.fatal) {
                        status.className = 'status error';
                        status.textContent = 'Stream error - Reconnecting...';
                        setTimeout(() => hls.loadSource(streamUrl), 2000);
                    }
                });
            }
            else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = streamUrl;
                video.addEventListener('loadedmetadata', () => {
                    status.textContent = 'Stream ready - Playing...';
                    video.play().catch(e => {
                        status.textContent = 'Click play to start streaming';
                    });
                });
            }
            else {
                status.className = 'status error';
                status.textContent = 'Your browser does not support HLS playback';
            }
        }

        initPlayer();
    </script>
</body>
</html>'''
    
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
        Initialize the stream processor with all required components
        
        Args:
            trello_api_key: API key for Trello access
            trello_token: Token for Trello authentication
            board_name: Name of the Trello board to use
            list_name: Name of the list containing the queue
            media_dir: Directory for storing downloaded media files
            cleanup_interval_hours: How often to run cleanup (in hours)
            max_storage_mb: Maximum storage limit in megabytes
            stream_port: Port number for the streaming server
            log_file: Path to the log file
        """
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
        
        # Set up Flask routes and create player page
        self._setup_flask_routes()
        self._create_player_page()
        
        self.is_running = False
        self.last_cleanup = time.time()
    
    def _setup_flask_routes(self) -> None:
        """
        Configure Flask routes with proper MIME types for both web and VLC playback.
        This method sets up routes for:
        1. The web player interface
        2. HLS playlist access
        3. Media segment delivery
        """
        
        @app.route('/')
        def index():
            """Serve the main player page"""
            return send_from_directory(str(self.config.hls_dir), 'player.html')

        @app.route('/stream/<path:filename>')
        def serve_hls(filename):
            """
            Serve HLS playlist and segments with appropriate MIME types.
            Handles different client types (browsers vs media players) correctly.
            """
            file_path = self.config.hls_dir / filename
            
            # Set content type based on file extension
            if filename.endswith('.m3u8'):
                mimetype = 'application/vnd.apple.mpegurl'
                response = send_from_directory(
                    str(self.config.hls_dir),
                    filename,
                    mimetype=mimetype
                )
                response.headers['Content-Type'] = mimetype
                response.headers['Content-Disposition'] = 'inline'
            elif filename.endswith('.ts'):
                # MPEG-2 Transport Stream segments
                mimetype = 'video/mp2t'
                response = send_from_directory(
                    str(self.config.hls_dir),
                    filename,
                    mimetype=mimetype
                )
            else:
                # Other static files (like the player page)
                response = send_from_directory(str(self.config.hls_dir), filename)
            
            # Add security headers
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            return response

    def _create_player_page(self) -> None:
        """Create the HTML5 player page with HLS.js support"""
        player_path = self.config.hls_dir / 'player.html'
        with open(player_path, 'w') as f:
            f.write(self.PLAYER_HTML)

    def start(self) -> None:
        """
        Start all processor components including web server and queue processing.
        This method initializes three daemon threads:
        1. Flask server for HLS streaming
        2. Queue processor for handling Trello cards
        3. Cleanup thread for managing storage
        """
        try:
            self.is_running = True
            
            # Start Flask server thread
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
        Stop all processor components and clean up resources.
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
        and processes them with continuous playback support.
        """
        while self.is_running:
            try:
                # Get all cards from Queue list
                queue_cards = self.trello.get_queue_cards()
                
                if queue_cards:
                    for card in queue_cards:
                        self.logger.info(f"Processing card: {card.name}")
                        
                        # Move card to Now Playing
                        self.trello.move_card_to_list(card, 'Now Playing')
                        
                        # Get media attachment
                        attachments = self.trello.get_card_attachments(card)
                        if not attachments:
                            self.logger.warning(f"No attachments found on card: {card.name}")
                            self.trello.move_card_to_list(card, 'Played')
                            continue
                        
                        # Download and validate the first attachment
                        attachment = attachments[0]
                        media_path = self.media.download_attachment(attachment)
                        
                        if not media_path:
                            self.logger.error(f"Failed to download attachment from card: {card.name}")
                            self.trello.move_card_to_list(card, 'Played')
                            continue
                        
                        # Get duration from card description if available
                        try:
                            duration = int(card.description) if card.description.strip().isdigit() else None
                        except (AttributeError, ValueError):
                            duration = None
                        
                        # Stream the media with continuous playback
                        self.media.stream_media(media_path, duration, wait_for_completion=True)
                        
                        # Move card to Played list after completion
                        self.trello.move_card_to_list(card, 'Played')
                        
                        # Check if cleanup is needed
                        if time.time() - self.last_cleanup > self.config.cleanup_interval:
                            self._cleanup_routine()
                
                time.sleep(5)  # Prevent excessive API calls
                
            except Exception as e:
                self.logger.error(f"Error in queue processing: {str(e)}")
                time.sleep(30)  # Wait longer on error

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