# web_server.py

from flask import Flask, send_from_directory, redirect, request, Response
from pathlib import Path
import logging
import time
import os
from typing import Tuple, Optional
from werkzeug.middleware.proxy_fix import ProxyFix

class StreamServer:
    """
    Handles the web server component for streaming media using HLS.
    Provides both web player access and direct HLS stream serving with
    comprehensive error handling and logging.
    """

    def __init__(self, hls_dir: Path, logger: logging.Logger):
        """
        Initialize the streaming server with enhanced logging and error handling

        Args:
            hls_dir: Directory containing HLS segments and playlists
            logger: Logger instance for detailed debugging
        """
        # Initialize core attributes
        self.app = Flask(__name__)
        self.hls_dir = hls_dir
        self.logger = logger

        # Support for running behind a proxy
        self.app.wsgi_app = ProxyFix(
            self.app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
        )

        # Log initialization
        self.logger.info(f"StreamServer initializing...")
        self.logger.info(f"HLS directory: {self.hls_dir.absolute()}")

        # Verify HLS directory exists and is accessible
        self._verify_hls_directory()

        # Set up routes and error handlers
        self._setup_routes()

        self.logger.info("StreamServer initialized successfully")

    def _verify_hls_directory(self) -> None:
        """
        Verify that the HLS directory exists and has proper permissions.
        Creates the directory if it doesn't exist.

        Raises:
            RuntimeError: If directory cannot be created or accessed
        """
        try:
            # Ensure directory exists
            self.hls_dir.mkdir(exist_ok=True)

            # Verify write permissions
            test_file = self.hls_dir / '.test_access'
            try:
                test_file.touch()
                test_file.unlink()
            except Exception as e:
                raise RuntimeError(f"No write permission in HLS directory: {str(e)}")

            self.logger.info("HLS directory verified")

        except Exception as e:
            self.logger.error(f"HLS directory verification failed: {str(e)}")
            raise

    def _is_vlc_client(self, user_agent: str) -> bool:
        """
        Check if the client is a media player that should receive direct HLS stream

        Args:
            user_agent: The User-Agent header from the request

        Returns:
            bool: True if client is a media player
        """
        media_players = ['vlc', 'mpv', 'mplayer', 'ffplay', 'quicktime']
        return any(player in user_agent.lower() for player in media_players)

    def _validate_file_access(self, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a requested file exists and is accessible
        Prevents directory traversal and ensures proper file permissions

        Args:
            filename: Name of the file to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Convert to Path object for safer path manipulation
            file_path = self.hls_dir / filename

            # Basic existence check
            if not file_path.exists():
                return False, f"File not found: {filename}"

            # Ensure file is actually a file (not directory)
            if not file_path.is_file():
                return False, f"Not a file: {filename}"

            # Prevent directory traversal
            try:
                file_path.relative_to(self.hls_dir)
            except ValueError:
                return False, "Invalid file path"

            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                return False, f"File not readable: {filename}"

            # Verify file extension
            if not filename.endswith(('.m3u8', '.ts')):
                return False, f"Invalid file type: {filename}"

            return True, None

        except Exception as e:
            self.logger.error(f"File validation error for {filename}: {str(e)}")
            return False, f"File validation error: {str(e)}"

    def _setup_routes(self) -> None:
        """
        Configure Flask routes with enhanced error handling and logging
        Sets up all endpoints needed for HLS streaming
        """

        @self.app.route('/')
        def index():
            """
            Root endpoint - serves player page or redirects to direct stream
            Handles different clients appropriately
            """
            try:
                # Get client information
                user_agent = request.headers.get('User-Agent', '')
                client_ip = request.remote_addr
                self.logger.info(f"Index request from {client_ip} - User-Agent: {user_agent}")

                # Handle media players differently
                if self._is_vlc_client(user_agent):
                    self.logger.info(f"Detected media player client, redirecting to direct stream")
                    return redirect('/stream/playlist.m3u8', code=302)

                # Serve web player
                player_path = self.hls_dir / 'player.html'
                if not player_path.exists():
                    self.logger.error("player.html not found in HLS directory")
                    return "Player not found", 404

                self.logger.debug(f"Serving web player to {client_ip}")
                return send_from_directory(str(self.hls_dir), 'player.html')

            except Exception as e:
                self.logger.error(f"Error handling index request: {str(e)}")
                return "Internal server error", 500

        @self.app.route('/stream/<path:filename>')
        def serve_hls(filename):
            """
            Serve HLS playlists and segments with proper MIME types
            Includes caching headers and error handling
            """
            try:
                # Log request details
                client_ip = request.remote_addr
                self.logger.debug(f"Stream request for {filename} from {client_ip}")

                # Validate file access
                is_valid, error_message = self._validate_file_access(filename)
                if not is_valid:
                    self.logger.error(f"File validation failed: {error_message}")
                    return error_message, 404

                # Set content type based on file type
                if filename.endswith('.m3u8'):
                    mimetype = 'application/vnd.apple.mpegurl'
                    self.logger.debug(f"Serving playlist: {filename}")
                elif filename.endswith('.ts'):
                    mimetype = 'video/mp2t'
                    self.logger.debug(f"Serving segment: {filename}")
                else:
                    self.logger.warning(f"Invalid file type requested: {filename}")
                    return "Invalid file type", 400

                # Serve the file with appropriate headers
                response = send_from_directory(
                    str(self.hls_dir),
                    filename,
                    mimetype=mimetype,
                    conditional=True  # Enable conditional requests
                )

                # Add streaming-specific headers
                response.headers.update({
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Range',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0',
                    'X-Content-Type-Options': 'nosniff'
                })

                # Add CORS headers for OPTIONS requests
                if request.method == 'OPTIONS':
                    return response

                # Log successful response
                self.logger.debug(f"Successfully served {filename} to {client_ip}")
                return response

            except Exception as e:
                self.logger.error(f"Error serving {filename}: {str(e)}")
                return f"Error serving file: {str(e)}", 500

        @self.app.after_request
        def after_request(response):
            """Log response details for debugging"""
            self.logger.debug(
                f"Response: {request.path} - {response.status_code} - "
                f"Size: {response.headers.get('Content-Length', 'unknown')}"
            )
            return response

        @self.app.errorhandler(404)
        def not_found_error(error):
            """Handle 404 errors with detailed logging"""
            self.logger.error(f"404 Error: {request.path} not found")
            return "File not found", 404

        @self.app.errorhandler(500)
        def internal_error(error):
            """Handle 500 errors with detailed logging"""
            self.logger.error(f"500 Error: {request.path} - {str(error)}")
            return "Internal server error", 500

    def _configure_app(self) -> None:
        """
        Configure Flask application settings for optimal streaming performance
        Sets up logging, caching, and security options
        """
        # Disable Flask's default logging in favor of our custom logger
        self.app.logger.handlers = []
        self.app.logger.propagate = True

        # Configure for production use
        self.app.config.update(
            ENV='production',
            DEBUG=False,
            TESTING=False,
            SEND_FILE_MAX_AGE_DEFAULT=0,  # Disable caching for HLS files
            MAX_CONTENT_LENGTH=None,  # No limit on file size
            PREFERRED_URL_SCHEME='http'
        )

        # Security settings
        self.app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=1800
        )

    def run(self, host: str = '0.0.0.0', port: int = 8080) -> None:
        """
        Start the Flask server with optimized settings for HLS streaming

        Args:
            host: Host address to bind to
            port: Port number to listen on
        """
        try:
            self.logger.info(f"Starting StreamServer on {host}:{port}")
            self._configure_app()

            # Configure server for streaming
            self.app.run(
                host=host,
                port=port,
                debug=False,
                use_reloader=False,
                threaded=True,
                processes=1
            )
        except Exception as e:
            self.logger.error(f"Failed to start server: {str(e)}")
            raise
