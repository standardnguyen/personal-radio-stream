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

# Create Flask app for serving HLS streams
app = Flask(__name__)

class StreamQueueProcessor:
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
        # Previous initialization code remains the same...
        
        # Stream settings
        self.stream_port = stream_port
        self.hls_dir = Path("hls_segments")
        self.hls_dir.mkdir(exist_ok=True)
        
        # Set up Flask routes
        @app.route('/stream/<path:filename>')
        def serve_hls(filename):
            return send_from_directory(str(self.hls_dir), filename)

    def start_hls_stream(self, media_path: str):
        """Start HLS stream with given media file"""
        try:
            if self.current_process:
                self.current_process.terminate()

            is_supported, file_type = self.check_file_type(media_path)
            is_audio = file_type in self.SUPPORTED_FORMATS['audio']

            # Create HLS streaming command
            command = [
                'ffmpeg',
                '-re',  # Read input at native framerate
                '-i', media_path,
                '-c:v', 'libx264' if not is_audio else 'copy',
                '-c:a', 'aac',
                '-f', 'hls',
                '-hls_time', '10',  # Segment length in seconds
                '-hls_list_size', '6',  # Number of segments to keep
                '-hls_flags', 'delete_segments',  # Auto-delete old segments
                '-hls_segment_filename', f'{self.hls_dir}/segment_%03d.ts',
                f'{self.hls_dir}/playlist.m3u8'
            ]

            self.current_process = subprocess.Popen(command)
            self.logger.info(f"Started HLS streaming: {media_path}")

        except Exception as e:
            self.logger.error(f"Failed to start stream: {str(e)}")
            raise

    def start(self):
        """Start the queue processor and web server"""
        self.is_running = True
        self.process_thread = Thread(target=self.process_queue)
        self.process_thread.start()
        
        # Start Flask server in a separate thread
        self.web_thread = Thread(target=lambda: app.run(
            host='0.0.0.0',
            port=self.stream_port,
            threaded=True
        ))
        self.web_thread.start()
        
        self.logger.info("Queue processor and web server started")
        print("Queue processor and web server started")

    def stop(self):
        """Stop the queue processor and web server"""
        self.is_running = False
        if self.current_process:
            self.current_process.terminate()
        self.process_thread.join()
        # Flask shutdown handled by the platform
        self.logger.info("Queue processor stopped")
        print("Queue processor stopped")