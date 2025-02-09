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
    Enhanced with detailed logging and segment verification.
    """

    def __init__(self, config, logger: logging.Logger):
        """
        Initialize the streamer with configuration and enhanced logging

        Args:
            config: Configuration object containing paths and settings
            logger: Configured logger instance for detailed logging
        """
        self.config = config
        self.logger = logger
        self.current_process: Optional[subprocess.Popen] = None
        self.current_media: Optional[Path] = None

        # Ensure HLS directory exists and is properly initialized
        self.hls_dir = self.config.hls_dir
        self.hls_dir.mkdir(exist_ok=True)
        self._clean_hls_dir()

        # Log critical paths and configurations
        self.logger.info(f"MediaStreamer initialized with HLS directory: {self.hls_dir.absolute()}")
        self._verify_ffmpeg_installation()

    def _verify_ffmpeg_installation(self) -> None:
        """Verify FFmpeg installation and codec support"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"Using FFmpeg version: {result.stdout.split(chr(10))[0]}")

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
        except Exception as e:
            self.logger.error(f"FFmpeg verification failed: {str(e)}")
            raise RuntimeError("FFmpeg verification failed") from e

    def _clean_hls_dir(self) -> None:
        """Clean up existing HLS segments and playlists"""
        try:
            count = 0
            for file in self.hls_dir.glob("*"):
                if file.is_file() and (file.suffix == '.ts' or file.suffix == '.m3u8'):
                    file.unlink()
                    count += 1
            self.logger.info(f"Cleaned HLS directory, removed {count} files")
        except Exception as e:
            self.logger.error(f"Error cleaning HLS directory: {str(e)}")
            raise

    def _verify_segments(self) -> bool:
        """
        Verify that HLS segments are being generated correctly

        Returns:
            bool: True if segments are present and valid
        """
        try:
            segments = list(self.hls_dir.glob("*.ts"))
            playlist = self.hls_dir / "playlist.m3u8"

            if not playlist.exists():
                self.logger.error("Playlist file not found")
                return False

            # Read playlist to verify it's properly formatted
            with open(playlist, 'r') as f:
                playlist_content = f.read()
                if not playlist_content.startswith('#EXTM3U'):
                    self.logger.error("Invalid playlist format")
                    return False

            if not segments:
                self.logger.error("No segments found")
                return False

            self.logger.info(f"Verified {len(segments)} segments and valid playlist")
            return True

        except Exception as e:
            self.logger.error(f"Error verifying segments: {str(e)}")
            return False

    def _monitor_stream_process(self, process: subprocess.Popen) -> None:
        """
        Monitor a streaming process and log its output

        Args:
            process: The subprocess.Popen instance to monitor
        """
        try:
            for line in process.stderr:
                if line.strip():
                    error_line = line.decode() if isinstance(line, bytes) else line
                    if "error" in error_line.lower():
                        self.logger.error(f"FFmpeg error: {error_line.strip()}")
                    else:
                        self.logger.debug(f"FFmpeg output: {error_line.strip()}")
        except Exception as e:
            self.logger.error(f"Error monitoring stream process: {str(e)}")

    def stop_stream(self) -> None:
        """Stop the current stream and clean up resources"""
        if self.current_process:
            try:
                self.logger.info("Stopping current stream...")
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.logger.warning("Stream process didn't terminate, forcing kill")
                    self.current_process.kill()
            except Exception as e:
                self.logger.error(f"Error stopping stream: {str(e)}")
            finally:
                self.current_process = None
                self.current_media = None
                self._clean_hls_dir()

    def stream_media(self, media_path: Path, duration: Optional[int] = None, wait_for_completion: bool = True) -> None:
        """
        Stream media file using FFmpeg with optimized HLS settings and enhanced monitoring

        Args:
            media_path: Path to the media file to stream
            duration: Optional duration in seconds to stream
            wait_for_completion: Whether to wait for the current file to finish
        """
        try:
            # Stop any existing stream and clean up
            self.stop_stream()

            # Determine and validate media type
            mime_type = magic.from_file(str(media_path), mime=True)
            media_type = MediaTypes.get_media_type(mime_type)

            if not media_type:
                raise ValueError(f"Unsupported media type: {mime_type}")

            self.logger.info(f"Preparing to stream {media_type} file: {media_path}")

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

            # Log the full command for debugging
            self.logger.info(f"FFmpeg command: {' '.join(map(str, command))}")

            # Start streaming process
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

            # Wait a short time and verify segments are being generated
            time.sleep(2)
            if not self._verify_segments():
                raise RuntimeError("Failed to generate HLS segments")

            # Handle stream duration and completion
            if duration:
                self.logger.info(f"Streaming for {duration} seconds")
                time.sleep(duration)
                self.stop_stream()
            elif wait_for_completion:
                self.logger.info("Waiting for stream to complete")
                self.current_process.wait()

        except Exception as e:
            self.logger.error(f"Error streaming media: {str(e)}")
            self.stop_stream()
            raise
