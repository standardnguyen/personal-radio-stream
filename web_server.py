# web_server.py

from flask import Flask, send_from_directory
from pathlib import Path

class StreamServer:
    """
    Handles the web server component for streaming media using HLS.
    Responsible for serving the web player and HLS streams.
    """
    
    def __init__(self, hls_dir: Path):
        """
        Initialize the streaming server
        
        Args:
            hls_dir: Directory containing HLS segments and playlists
        """
        self.app = Flask(__name__)
        self.hls_dir = hls_dir
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Configure Flask routes with proper MIME types for both web and VLC playback"""
        
        @self.app.route('/')
        def index():
            """Serve the main player page"""
            return send_from_directory(str(self.hls_dir), 'player.html')

        @self.app.route('/stream/<path:filename>')
        def serve_hls(filename):
            """Serve HLS playlist and segments with appropriate MIME types"""
            # Set content type based on file extension
            if filename.endswith('.m3u8'):
                mimetype = 'application/vnd.apple.mpegurl'
                response = send_from_directory(
                    str(self.hls_dir),
                    filename,
                    mimetype=mimetype
                )
                response.headers['Content-Type'] = mimetype
                response.headers['Content-Disposition'] = 'inline'
            elif filename.endswith('.ts'):
                # MPEG-2 Transport Stream segments
                mimetype = 'video/mp2t'
                response = send_from_directory(
                    str(self.hls_dir),
                    filename,
                    mimetype=mimetype
                )
            else:
                # Other static files (like the player page)
                response = send_from_directory(str(self.hls_dir), filename)
            
            # Add security headers
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            return response
    
    def run(self, host: str = '0.0.0.0', port: int = 8080) -> None:
        """Start the Flask server"""
        self.app.run(host=host, port=port, debug=False, use_reloader=False)