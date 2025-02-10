from flask import Flask, send_from_directory, jsonify, send_file
from pathlib import Path
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
from media_manager import MediaManager

class StreamServer:
    def __init__(self, media_dir: Path, logger: logging.Logger, trello_manager=None):
        self.app = Flask(__name__)
        self.media_dir = media_dir
        self.logger = logger
        self.trello = trello_manager
        # Initialize MediaManager if Trello is provided
        self.media_manager = MediaManager(trello_manager.config, logger) if trello_manager else None
        
        # Use ProxyFix if behind a proxy
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
            """
            Build a playlist from Trello cards.
            For the first two cards, pre-download the attachment;
            for the remaining cards, just compute the safe filename without downloading.
            """
            if not self.trello:
                return jsonify([])
            
            cards = self.trello.get_queue_cards()
            playlist = []
            for i, card in enumerate(cards):
                attachments = card.get_attachments()
                if attachments:
                    att = attachments[0]
                    # Compute a safe filename similar to the logic in download_attachment:
                    safe_filename = "".join(x for x in Path(att.name).stem if x.isalnum() or x in "._- ")
                    safe_filename += Path(att.name).suffix
                    if i < 2:
                        # Pre-download the first two songs
                        file_path = self.media_manager.download_attachment(att)
                        if file_path:
                            filename = file_path.name
                        else:
                            # If download fails, fall back to the safe filename.
                            filename = safe_filename
                    else:
                        # For the rest, do not pre-download.
                        # (If the file exists from a previous run, it will be served;
                        # otherwise, it will be lazy-loaded by the client.)
                        filename = safe_filename
                    playlist.append({
                        'id': card.id,
                        'name': card.name,
                        'filename': filename
                    })
                else:
                    playlist.append({
                        'id': card.id,
                        'name': card.name,
                        'filename': None
                    })
            return jsonify(playlist)

        @self.app.route('/media/<path:filename>')
        def serve_media(filename):
            try:
                # Replace any plus signs with spaces if needed
                filename = filename.replace('+', ' ')
                self.logger.info(f"Serving file from {self.media_dir}: {filename}")
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
