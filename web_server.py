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
            Just compute filenames without downloading - files will be downloaded when requested.
            """
            if not self.trello:
                return jsonify([])

            try:
                cards = self.trello.get_queue_cards()
                playlist = []

                for card in cards:
                    try:
                        attachments = card.get_attachments()
                        if attachments:
                            att = attachments[0]
                            # Compute a safe filename
                            safe_filename = "".join(x for x in Path(att.name).stem if x.isalnum() or x in "._- ")
                            safe_filename += Path(att.name).suffix

                            playlist.append({
                                'id': card.id,
                                'name': card.name,
                                'filename': safe_filename
                            })
                        else:
                            playlist.append({
                                'id': card.id,
                                'name': card.name,
                                'filename': None
                            })
                    except Exception as card_error:
                        self.logger.error(f"Error processing card {card.name}: {str(card_error)}")
                        continue

                return jsonify(playlist)

            except Exception as e:
                self.logger.error(f"Error building playlist: {str(e)}")
                return jsonify({'error': 'Failed to build playlist'}), 500

        @self.app.route('/media/<path:filename>')
        def serve_media(filename):
            """
            Serve media files from the media directory.
            If file doesn't exist, try to download it first.
            """
            try:
                # Replace any plus signs with spaces if needed
                filename = filename.replace('+', ' ')
                file_path = self.media_dir / filename

                # If file doesn't exist, try to download it
                if not file_path.exists() and self.trello:
                    self.logger.info(f"File not found locally, attempting to download: {filename}")
                    # Find the corresponding card and attachment
                    cards = self.trello.get_queue_cards()
                    for card in cards:
                        attachments = card.get_attachments()
                        if attachments:
                            att = attachments[0]
                            safe_filename = "".join(x for x in Path(att.name).stem if x.isalnum() or x in "._- ")
                            safe_filename += Path(att.name).suffix
                            if safe_filename == filename:
                                # Found the matching attachment, download it
                                downloaded_path = self.media_manager.download_attachment(att)
                                if downloaded_path:
                                    file_path = downloaded_path
                                    break

                if not file_path.exists():
                    self.logger.error(f"File not found and could not be downloaded: {filename}")
                    return "File not found", 404

                self.logger.info(f"Serving file: {filename}")
                return send_from_directory(self.media_dir, filename)
            except Exception as e:
                self.logger.error(f"Error serving {filename}: {str(e)}")
                return "Error serving file", 500

        @self.app.route('/api/queue/status')
        def get_queue_status():
            """Get status of the current queue including download progress"""
            try:
                if not self.media_manager:
                    return jsonify({'error': 'Media manager not initialized'}), 500

                current_media = self.media_manager.current_media
                return jsonify({
                    'current_track': str(current_media) if current_media else None,
                })
            except Exception as e:
                self.logger.error(f"Error getting queue status: {str(e)}")
                return jsonify({'error': 'Failed to get queue status'}), 500

        @self.app.errorhandler(404)
        def not_found_error(error):
            return "Not found", 404

        @self.app.errorhandler(500)
        def internal_error(error):
            return "Internal server error", 500

    def run(self, host: str = '0.0.0.0', port: int = 8080):
        """Start the Flask server"""
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
