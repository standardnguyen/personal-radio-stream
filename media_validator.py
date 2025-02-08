# media_validator.py

import subprocess
import logging
from typing import Tuple
from pathlib import Path

class MediaValidator:
    """Handles validation of media files using FFmpeg tools"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._verify_ffmpeg_installation()
    
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
            self.logger.info(f"FFmpeg version: {result.stdout.split(chr(10))[0]}")
            
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
    
    def validate_audio_file(self, file_path: Path, mime_type: str) -> Tuple[bool, str]:
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
                str(file_path)
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
                    '-i', str(file_path),
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