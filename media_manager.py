# media_manager.py

import time
import subprocess
import requests
import magic
from pathlib import Path
from typing import Optional, Dict, List
from config_manager import StreamConfig
import logging
import shutil
from threading import Thread

class MediaManager:
    """
    Handles all media-related operations including downloading, format validation,
    transcoding, and streaming of media files from Trello attachments.
    
    This implementation includes optimized streaming configurations for stable playback
    across different clients (especially VLC), efficient media cleanup, and robust
    error handling.
    """
    
    # Define supported media formats with their MIME types
    SUPPORTED_FORMATS = {
        'video': [
            'video/mp4', 'video/mpeg', 'video/avi', 'video/x-matroska',
            'video/webm', 'video/quicktime', 'video/x-flv'
        ],
        'audio': [
            'audio/mpeg', 'audio/wav',  'audio/x-wav', 'audio/aac', 'audio/ogg',
            'audio/flac', 'audio/x-m4a', 'audio/mp4'
        ]
    }
    
    # FFmpeg preset configurations for different media types
    FFMPEG_PRESETS = {
        'video': {
            'codec': 'libx264',
            'preset': 'veryfast',
            'crf': '23',
            'audio_codec': 'aac',
            'audio_bitrate': '128k',
            'audio_rate': '44100'
        },
        'audio': {
            'codec': 'aac',
            'bitrate': '192k',
            'sample_rate': '44100'
        }
    }
    
    def __init__(self, config: StreamConfig, logger: logging.Logger):
        """
        Initialize the media manager with configuration and logging
        
        Args:
            config: StreamConfig instance containing all necessary settings
            logger: Configured logger instance for error and info logging
        """
        self.config = config
        self.logger = logger
        self.current_process: Optional[subprocess.Popen] = None
        
        # Set up the HLS segments directory
        self.hls_dir = self.config.hls_dir
        self.hls_dir.mkdir(exist_ok=True)
        
        # Create an authenticated session for Trello API requests
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'OAuth oauth_consumer_key="{config.trello_api_key}", oauth_token="{config.trello_token}"'
        })
        
        # Initialize media tracking
        self._verify_ffmpeg_installation()
        self.current_media: Optional[Path] = None
    
    def _verify_ffmpeg_installation(self) -> None:
        """
        Verify that FFmpeg is installed and accessible
        
        Raises:
            RuntimeError: If FFmpeg is not found or not executable
        """
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            raise RuntimeError("FFmpeg is not installed or not accessible") from e
    
    def _get_media_type(self, mime_type: str) -> Optional[str]:
        """
        Determine if a file is video or audio based on its MIME type
        
        Args:
            mime_type: The MIME type string to check
            
        Returns:
            str: Either 'video' or 'audio' if supported, None if unsupported
        """
        for media_type, formats in self.SUPPORTED_FORMATS.items():
            if mime_type in formats:
                return media_type
        return None
    
    def _is_supported_format(self, mime_type: str) -> bool:
        """
        Check if a given MIME type is in our supported formats list
        
        Args:
            mime_type: The MIME type string to check (e.g., 'audio/mp3')
            
        Returns:
            bool: True if the format is supported, False otherwise
        """
        return self._get_media_type(mime_type) is not None
    
    def download_attachment(self, attachment) -> Optional[Path]:
        """
        Download and validate a media attachment from Trello
        
        Args:
            attachment: Trello attachment object containing url and name
            
        Returns:
            Path: Path to the downloaded file if successful
            None: If download or validation fails
        """
        try:
            # Generate safe filename from attachment name
            filename = Path(attachment.name).stem
            safe_filename = "".join(x for x in filename if x.isalnum() or x in "._- ")
            file_path = self.config.media_dir / f"{safe_filename}{Path(attachment.name).suffix}"
            
            # Download file using authenticated session with progress tracking
            self.logger.info(f"Downloading attachment: {attachment.name}")
            response = self.session.get(attachment.url, stream=True)
            response.raise_for_status()
            
            file_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            # Save file in chunks to handle large files efficiently
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Log download progress for large files
                        if file_size > 10 * 1024 * 1024:  # 10MB
                            progress = (downloaded / file_size) * 100
                            if progress % 10 == 0:  # Log every 10%
                                self.logger.info(f"Download progress: {progress:.1f}%")
            
            # Validate the downloaded file's media type
            mime_type = magic.from_file(str(file_path), mime=True)
            if not self._is_supported_format(mime_type):
                self.logger.error(f"Unsupported media type: {mime_type}")
                file_path.unlink()
                return None
            
            self.logger.info(f"Successfully downloaded and validated: {file_path}")
            return file_path
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error downloading attachment: {str(e)}")
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                self.logger.error("Authentication failed. Please verify your Trello API key and token.")
            return None
        except Exception as e:
            self.logger.error(f"Error downloading attachment: {str(e)}")
            return None
    
    def stream_media(self, media_path: Path, duration: Optional[int] = None, wait_for_completion: bool = True) -> None:
        """
        Stream media file using FFmpeg with optimized HLS settings for stable playback.
        
        This implementation includes several improvements for stable streaming:
        - Longer segment duration and larger playlist size for better buffering
        - Optimized encoding settings for real-time streaming
        - Separate handling for video and audio content
        - Improved error handling and cleanup
        
        Args:
            media_path: Path to the media file to stream
            duration: Optional duration in seconds to stream
            wait_for_completion: Whether to wait for the current file to finish
        """
        try:
            # Stop any existing stream
            self.stop_stream()
            
            # Clean up any existing HLS segments
            for file in self.hls_dir.glob("*.ts"):
                file.unlink()
            
            # Determine media type
            mime_type = magic.from_file(str(media_path), mime=True)
            media_type = self._get_media_type(mime_type)
            
            if not media_type:
                raise ValueError(f"Unsupported media type: {mime_type}")
            
            # Build FFmpeg command with optimized settings
            command = ['ffmpeg', '-y']  # Overwrite output files
            
            # Input settings
            command.extend([
                '-re',                # Read input at native framerate
                '-i', str(media_path)
            ])
            
            # Media-specific encoding settings
            if media_type == 'video':
                preset = self.FFMPEG_PRESETS['video']
                command.extend([
                    # Video settings
                    '-c:v', preset['codec'],
                    '-preset', preset['preset'],
                    '-tune', 'zerolatency',
                    '-profile:v', 'main',
                    '-level', '3.1',
                    '-crf', preset['crf'],
                    '-bufsize', '8192k',
                    '-maxrate', '4096k',
                    
                    # Audio settings
                    '-c:a', preset['audio_codec'],
                    '-b:a', preset['audio_bitrate'],
                    '-ar', preset['audio_rate'],
                ])
            else:  # audio
                preset = self.FFMPEG_PRESETS['audio']
                command.extend([
                    '-c:a', preset['codec'],
                    '-b:a', preset['bitrate'],
                    '-ar', preset['sample_rate']
                ])
            
            # HLS specific settings for continuous playback
            command.extend([
                '-f', 'hls',
                '-hls_time', '6',             # Segment duration
                '-hls_list_size', '15',       # Number of segments in playlist
                '-hls_flags', 'delete_segments+independent_segments+append_list',
                '-hls_segment_type', 'mpegts',
                '-hls_init_time', '4',
                '-hls_playlist_type', 'event',
                '-hls_segment_filename', 
                str(self.hls_dir / 'segment_%03d.ts')
            ])
            
            # Output playlist
            command.append(str(self.hls_dir / 'playlist.m3u8'))
            
            # Start streaming process
            self.logger.info(f"Starting optimized stream for: {media_path}")
            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.current_media = media_path
            
            # Monitor process for errors
            error_thread = Thread(
                target=self._monitor_stream_process,
                args=(self.current_process,),
                daemon=True
            )
            error_thread.start()
            
            # Handle stream duration and completion
            if duration:
                time.sleep(duration)
                self.stop_stream()
            elif wait_for_completion:
                self.current_process.wait()
            
        except Exception as e:
            self.logger.error(f"Error streaming media: {str(e)}")
            self.stop_stream()
    
    def _monitor_stream_process(self, process: subprocess.Popen) -> None:
        """
        Monitor the FFmpeg process for errors and log them
        
        Args:
            process: The FFmpeg subprocess to monitor
        """
        try:
            stderr = process.stderr
            while process.poll() is None and stderr:
                line = stderr.readline().decode().strip()
                if line and ('error' in line.lower() or 'failed' in line.lower()):
                    self.logger.error(f"FFmpeg error: {line}")
        except Exception as e:
            self.logger.error(f"Error monitoring stream process: {str(e)}")
    
    def stop_stream(self) -> None:
        """
        Stop the current stream if one is running and clean up resources
        """
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            finally:
                self.current_process = None
                self.current_media = None
            
            self.logger.info("Stream stopped")
            
            # Clean up HLS segments
            try:
                for file in self.hls_dir.glob("*.ts"):
                    file.unlink()
            except Exception as e:
                self.logger.error(f"Error cleaning up HLS segments: {str(e)}")
    
    def cleanup_media(self) -> None:
        """
        Remove old media files to maintain storage limits.
        Implements a more sophisticated cleanup strategy:
        - Deletes oldest files first when storage limit is exceeded
        - Keeps track of recently played files
        - Ensures cleanup doesn't affect currently playing media
        """
        try:
            total_size = 0
            files: List[tuple[Path, int]] = []
            
            # Calculate total size and gather file info
            for file in self.config.media_dir.glob("*"):
                if file.is_file():
                    size = file.stat().st_size
                    files.append((file, size))
                    total_size += size
            
            # Sort files by modification time (oldest first)
            files.sort(key=lambda x: x[0].stat().st_mtime)
            
            # Remove oldest files until under storage limit
            while total_size > self.config.max_storage and files:
                file, size = files.pop(0)
                
                # Skip currently playing file
                if self.current_media and file.samefile(self.current_media):
                    continue
                
                try:
                    file.unlink()
                    total_size -= size
                    self.logger.info(f"Cleaned up: {file.name}")
                except Exception as e:
                    self.logger.error(f"Error deleting {file}: {str(e)}")
            
            # Log storage status
            self.logger.info(f"Storage usage after cleanup: {total_size / 1024 / 1024:.1f}MB")
                    
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")

from threading import Thread