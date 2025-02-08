# media_manager.py

import time
import subprocess
import requests
import magic
from pathlib import Path
from typing import Optional, Dict, List, Tuple
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
    error handling with specific improvements for MP3 handling.
    """
    
    # Define supported media formats with their MIME types
    SUPPORTED_FORMATS = {
        'video': [
            'video/mp4', 'video/mpeg', 'video/avi', 'video/x-matroska',
            'video/webm', 'video/quicktime', 'video/x-flv'
        ],
        'audio': [
            'audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/aac', 'audio/ogg',
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
            'mp3': {  # Specific settings for MP3 files
                'input_flags': [
                    '-analyzeduration', '10M',  # Increased analysis time for complex MP3s
                    '-probesize', '10M'         # Increased probe size for VBR files
                ],
                'output_flags': [
                    '-c:a', 'aac',              # Convert to AAC for HLS
                    '-b:a', '192k',             # Higher bitrate for quality
                    '-ar', '44100',             # Standard sample rate
                    '-af', 'aresample=async=1000', # Handle async audio
                    '-ac', '2',                 # Ensure stereo output
                    '-map', '0:a'               # Explicitly map audio stream
                ]
            },
            'default': {  # Default settings for other audio formats
                'codec': 'aac',
                'bitrate': '192k',
                'sample_rate': '44100'
            }
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
        Verify that FFmpeg is installed and accessible with proper codecs
        
        Raises:
            RuntimeError: If FFmpeg is not found or not executable
        """
        try:
            # Check FFmpeg version and available codecs
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"FFmpeg version: {result.stdout.split('\\n')[0]}")
            
            # Verify codec support
            codecs = subprocess.run(
                ['ffmpeg', '-codecs'],
                capture_output=True,
                text=True,
                check=True
            )
            required_codecs = ['aac', 'libx264']
            for codec in required_codecs:
                if codec not in codecs.stdout:
                    self.logger.warning(f"Required codec {codec} may not be available")
                    
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
    
    def _validate_audio_file(self, file_path: str, mime_type: str) -> Tuple[bool, str]:
        """
        Validate audio file using FFprobe, with specific checks for MP3s
        
        Args:
            file_path: Path to the audio file
            mime_type: MIME type of the file
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            # Use FFprobe to analyze the file
            probe_command = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'a:0',  # Select first audio stream
                '-show_entries', 'stream=codec_name,channels,sample_rate',
                '-of', 'json',
                file_path
            ]
            
            result = subprocess.run(
                probe_command,
                capture_output=True,
                text=True,
                check=True
            )
            
            if "stream" not in result.stdout:
                return False, "No audio stream found in file"
            
            # Additional checks for MP3 files
            if mime_type == 'audio/mpeg':
                # Check for common MP3 corruption indicators
                check_command = [
                    'ffmpeg',
                    '-v', 'error',
                    '-i', file_path,
                    '-f', 'null',
                    '-'
                ]
                check_result = subprocess.run(
                    check_command,
                    capture_output=True,
                    text=True
                )
                
                if check_result.stderr:
                    if "Invalid data found when processing input" in check_result.stderr:
                        return False, "MP3 file appears to be corrupted"
                        
            return True, "Audio file validated successfully"
            
        except subprocess.CalledProcessError as e:
            return False, f"FFprobe validation failed: {e.stderr}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
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
            
            # Additional validation for audio files
            media_type = self._get_media_type(mime_type)
            if media_type == 'audio':
                is_valid, error_message = self._validate_audio_file(str(file_path), mime_type)
                if not is_valid:
                    self.logger.error(f"Audio validation failed: {error_message}")
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
        - Special handling for MP3 files
        
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
            
            # Input settings with special handling for MP3
            if media_type == 'audio' and mime_type == 'audio/mpeg':
                command.extend(self.FFMPEG_PRESETS['audio']['mp3']['input_flags'])
            
            command.extend(['-i', str(media_path)])
            
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
                if mime_type == 'audio/mpeg':
                    # Special handling for MP3 files
                    command.extend(self.FFMPEG_PRESETS['audio']['mp3']['output_flags'])
                else:
                    # Default audio settings for other formats
                    preset = self.FFMPEG_PRESETS['audio']['default']
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
            
        except Exception as e