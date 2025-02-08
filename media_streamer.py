# media_streamer.py

import subprocess
import logging
import time
import magic
from pathlib import Path
from typing import Optional
from threading import Thread
from media_types import MediaTypes
from media_config import FFmpegConfig

class MediaStreamer:
    """
    Handles media streaming using FFmpeg with optimized HLS settings.
    Provides stable playback across different clients with proper error handling.
    """
    
    def __init__(self, config, logger: logging.Logger):
        """
        Initialize the streamer with configuration
        
        Args:
            config: Configuration object containing paths and settings
            logger: Configured logger instance
        """
        self.config = config
        self.logger = logger
        self.current_process: Optional[subprocess.Popen] = None
        self.current_media: Optional[Path] = None
        
        # Ensure HLS directory exists
        self.hls_dir = self.config.hls_dir
        self.hls_dir.mkdir(exist_ok=True)
    
    def _monitor_stream_process(self, process: subprocess.Popen) -> None:
        """
        Monitor a streaming process for errors and log them
        
        Args:
            process: The subprocess.Popen instance to monitor
        """
        try:
            for line in process.stderr:
                if line.strip():
                    # Log only non-empty lines, converting bytes to string if needed
                    error_line = line.decode() if isinstance(line, bytes) else line
                    if "error" in error_line.lower():
                        self.logger.error(f"FFmpeg error: {error_line.strip()}")
                    else:
                        self.logger.debug(f"FFmpeg output: {error_line.strip()}")
        except Exception as e:
            self.logger.error(f"Error monitoring stream process: {str(e)}")
    
    def stop_stream(self) -> None:
        """Stop the current stream if one is running"""
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            finally:
                self.current_process = None
                self.current_media = None
    
    def stream_media(self, media_path: Path, duration: Optional[int] = None, wait_for_completion: bool = True) -> None:
        """
        Stream media file using FFmpeg with optimized HLS settings
        
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
            media_type = MediaTypes.get_media_type(mime_type)
            
            if not media_type:
                raise ValueError(f"Unsupported media type: {mime_type}")
            
            # Build FFmpeg command with optimized settings
            command = ['ffmpeg', '-y']  # Overwrite output files
            
            # Input settings with special handling for MP3
            if media_type == 'audio' and mime_type == 'audio/mpeg':
                command.extend(FFmpegConfig.get_mp3_input_flags())
            
            command.extend(['-i', str(media_path)])
            
            # Media-specific encoding settings
            if media_type == 'video':
                command.extend(FFmpegConfig.get_video_settings())
            else:  # audio
                command.extend(FFmpegConfig.get_audio_settings(mime_type))
            
            # Add HLS settings
            command.extend(FFmpegConfig.HLS_SETTINGS)
            command.extend([
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
            raise