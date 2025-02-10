from flask import Flask, send_from_directory, jsonify, send_file
from pathlib import Path
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
import io
from media_manager import MediaManager

class StreamServer:
    def __init__(self, media_dir: Path, logger: logging.Logger, trello_manager=None):
        self.app = Flask(__name__)
        self.media_dir = media_dir
        self.logger = logger
        self.trello = trello_manager
        self.media_manager = MediaManager(trello_manager.config, logger) if trello_manager else None
        
        # Support for running behind a proxy
        self.app.wsgi_app = ProxyFix(
            self.app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
        )

        self._setup_routes()
        self.logger.info("StreamServer initialized")

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return send_from_directory('templates', 'index.html')

        @self.app.route('/api/playlist')
        def get_playlist():
            if not self.trello:
                return jsonify([])
            
            cards = self.trello.get_queue_cards()
            playlist = []
            for card in cards:
                attachments = card.get_attachments()
                if attachments:
                    # Download the attachment
                    file_path = self.media_manager.download_attachment(attachments[0])
                    filename = file_path.name if file_path else None
                else:
                    filename = None
                playlist.append({
                    'id': card.id,
                    'name': card.name,
                    'filename': filename
                })
            return jsonify(playlist)

        @self.app.route('/media/<path:filename>')
        def serve_media(filename):
            try:
                filename = filename.replace('+', ' ')
                return send_from_directory(self.media_dir, filename)
            except Exception as e:
                self.logger.error(f"Error serving {filename}: {str(e)}")
                return "Error serving file", 500


        @self.app.errorhandler(404)
        def not_found_error(error):
            return "Not found", 404

        @self.app.errorhandler(500)
        def internal_error(error):
            return "Internal server error", 500

    def run(self, host: str = '0.0.0.0', port: int = 8080):
        try:
            self.logger.info(f"Starting StreamServer on {host}:{port}")
            self.app.run(
                host=host,
                port=port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"Failed to start server: {str(e)}")
            raise