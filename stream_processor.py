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

class StreamQueueProcessor:
    # Supported media formats
    SUPPORTED_FORMATS = {
        'video': [
            'video/mp4',
            'video/mpeg',
            'video/x-msvideo',  # AVI
            'video/x-matroska',  # MKV
            'video/webm',
            'video/quicktime',  # MOV
            'video/x-flv'
        ],
        'audio': [
            'audio/mpeg',  # MP3
            'audio/wav',
            'audio/x-wav',
            'audio/aac',
            'audio/ogg',
            'audio/flac',
            'audio/x-m4a'
        ]
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
        stream_url: str = "rtsp://0.0.0.0:8554/live",
        log_file: str = "stream_processor.log"
    ):
        # Set up logging
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Initialize Trello client
        try:
            self.client = TrelloClient(
                api_key=trello_api_key,
                token=trello_token
            )
            self.board = next(board for board in self.client.list_boards() 
                            if board.name == board_name)
            self.queue_list = next(list_ for list_ in self.board.list_lists() 
                                if list_.name == list_name)
        except Exception as e:
            self.logger.error(f"Failed to initialize Trello client: {str(e)}")
            raise

        # Stream settings
        self.stream_url = stream_url
        self.current_process = None
        self.is_running = False

        # Media management settings
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(exist_ok=True)
        self.cleanup_interval = cleanup_interval_hours * 3600
        self.max_storage = max_storage_mb * 1024 * 1024
        self.last_cleanup = time.time()

    def check_file_type(self, file_path: str) -> Tuple[bool, str]:
        """Verify if file is a supported media format"""
        try:
            mime = magic.Magic(mime=True)
            file_type = mime.from_file(str(file_path))
            is_supported = (file_type in self.SUPPORTED_FORMATS['video'] or 
                        file_type in self.SUPPORTED_FORMATS['audio'])
            return is_supported, file_type
        except Exception as e:
            self.logger.error(f"File type check failed: {str(e)}")
            return False, "unknown"

    def get_attachment(self, card) -> Optional[str]:
        """Get the first media attachment from a card"""
        try:
            attachments = card.get_attachments()
            if not attachments:
                card.comment("Error: No attachments found")
                return None

            attachment = attachments[0]
            file_ext = Path(attachment.file_name).suffix.lower()
            
            if not any(ext in file_ext for ext in ['.mp4', '.avi', '.mkv', '.mov', 
                                                '.mp3', '.wav', '.aac', '.ogg', '.flac']):
                card.comment(f"Unsupported file type: {file_ext}")
                return None

            local_path = self.media_dir / attachment.file_name

            # Storage check
            if self.get_directory_size() + attachment.size > self.max_storage:
                self.emergency_cleanup()
                if self.get_directory_size() + attachment.size > self.max_storage:
                    card.comment("Error: Not enough storage space")
                    return None

            # Download with progress tracking
            response = requests.get(attachment.url, stream=True)
            total_size = int(response.headers.get('content-length', 0))

            with open(local_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded += len(chunk)
                        f.write(chunk)
                        if total_size and downloaded % (total_size // 5) < 8192:
                            progress = (downloaded / total_size) * 100
                            card.comment(f"Download progress: {progress:.1f}%")

            # Verify downloaded file
            is_supported, file_type = self.check_file_type(local_path)
            if not is_supported:
                local_path.unlink()
                card.comment(f"Unsupported media type: {file_type}")
                return None

            self.logger.info(f"Successfully downloaded: {attachment.file_name}")
            return str(local_path)

        except Exception as e:
            self.logger.error(f"Attachment download failed: {str(e)}")
            card.comment(f"Error getting attachment: {str(e)}")
            return None

    def get_directory_size(self) -> int:
        """Get total size of media directory in bytes"""
        try:
            return sum(f.stat().st_size for f in self.media_dir.rglob('*') if f.is_file())
        except Exception as e:
            self.logger.error(f"Failed to get directory size: {str(e)}")
            return 0

    def emergency_cleanup(self):
        """Aggressive cleanup when storage limit is reached"""
        try:
            files = sorted(
                [(f, f.stat().st_mtime) for f in self.media_dir.glob('*') if f.is_file()],
                key=lambda x: x[1]
            )

            target_size = self.max_storage * 0.8
            for file_path, _ in files:
                if self.get_directory_size() < target_size:
                    break
                file_path.unlink()
                self.logger.info(f"Emergency cleanup: Deleted {file_path}")

        except Exception as e:
            self.logger.error(f"Emergency cleanup failed: {str(e)}")

    def cleanup_old_media(self):
        """Regular cleanup of old media files"""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        try:
            for media_file in self.media_dir.glob('*'):
                if media_file.is_file():
                    age = current_time - media_file.stat().st_mtime
                    if age > self.cleanup_interval:
                        media_file.unlink()
                        self.logger.info(f"Cleaned up old file: {media_file}")

            if self.get_directory_size() > self.max_storage * 0.9:
                self.emergency_cleanup()

            self.last_cleanup = current_time

        except Exception as e:
            self.logger.error(f"Cleanup failed: {str(e)}")

    def start_vlc_stream(self, media_path: str):
        """Start VLC stream with given media file"""
        try:
            if self.current_process:
                self.current_process.terminate()

            is_supported, file_type = self.check_file_type(media_path)
            is_audio = file_type in self.SUPPORTED_FORMATS['audio']

            command = [
                'cvlc',
                media_path,
                '--sout', 
                f'#transcode{{{
                    "acodec=mp3,ab=128,channels=2,samplerate=44100" if is_audio else
                    "vcodec=h264,scale=1,acodec=mp3,ab=128,channels=2,samplerate=44100"
                }}}:rtp{{dst=0.0.0.0,port=8554,sdp={self.stream_url}}}',
                '--loop',
                '--no-video-title-show'
            ]

            self.current_process = subprocess.Popen(command)
            self.logger.info(f"Started streaming: {media_path}")

        except Exception as e:
            self.logger.error(f"Failed to start stream: {str(e)}")
            raise

    def process_queue(self):
        """Main queue processing loop"""
        while self.is_running:
            try:
                cards = self.queue_list.list_cards()

                if cards:
                    current_card = cards[0]
                    local_path = self.get_attachment(current_card)

                    if local_path and os.path.exists(local_path):
                        self.logger.info(f"Processing card: {current_card.name}")
                        self.start_vlc_stream(local_path)

                        # Move to Now Playing
                        playing_list = next(list_ for list_ in self.board.list_lists() 
                                        if list_.name == "Now Playing")
                        current_card.change_list(playing_list.id)

                        # Get duration from description or default
                        try:
                            duration = float(current_card.description.strip() or 60)
                        except ValueError:
                            duration = 60

                        time.sleep(duration)

                        # Move to Played
                        played_list = next(list_ for list_ in self.board.list_lists() 
                                        if list_.name == "Played")
                        current_card.change_list(played_list.id)
                    else:
                        current_card.comment("Error: Could not process media file")

                self.cleanup_old_media()
                time.sleep(5)

            except Exception as e:
                self.logger.error(f"Queue processing error: {str(e)}")
                time.sleep(5)  # Wait before retrying

    def start(self):
        """Start the queue processor"""
        self.is_running = True
        self.process_thread = Thread(target=self.process_queue)
        self.process_thread.start()
        self.logger.info("Queue processor started")
        print("Queue processor started")

    def stop(self):
        """Stop the queue processor"""
        self.is_running = False
        if self.current_process:
            self.current_process.terminate()
        self.process_thread.join()
        self.logger.info("Queue processor stopped")
        print("Queue processor stopped")

if __name__ == "__main__":
    import configparser
    
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    processor = StreamQueueProcessor(
        trello_api_key=config['Trello']['api_key'],
        trello_token=config['Trello']['token'],
        board_name=config['Trello']['board_name'],
        list_name=config['Trello']['list_name'],
        media_dir=config['Storage'].get('media_dir', 'downloaded_media'),
        cleanup_interval_hours=int(config['Storage'].get('cleanup_hours', '24')),
        max_storage_mb=int(config['Storage'].get('max_storage_mb', '5000')),
        stream_url=config['Stream'].get('url', 'rtsp://0.0.0.0:8554/live')
    )
    
    try:
        processor.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        processor.stop()