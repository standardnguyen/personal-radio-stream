# media_config.py

class FFmpegConfig:
    """Defines FFmpeg preset configurations for different media types"""
    
    PRESETS = {
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
    
    HLS_SETTINGS = [
        '-f', 'hls',
        '-hls_time', '6',             # Segment duration
        '-hls_list_size', '15',       # Number of segments in playlist
        '-hls_flags', 'delete_segments+independent_segments+append_list',
        '-hls_segment_type', 'mpegts',
        '-hls_init_time', '4',
        '-hls_playlist_type', 'event'
    ]
    
    @classmethod
    def get_video_settings(cls):
        """Get FFmpeg command arguments for video encoding"""
        preset = cls.PRESETS['video']
        return [
            '-c:v', preset['codec'],
            '-preset', preset['preset'],
            '-tune', 'zerolatency',
            '-profile:v', 'main',
            '-level', '3.1',
            '-crf', preset['crf'],
            '-bufsize', '8192k',
            '-maxrate', '4096k',
            '-c:a', preset['audio_codec'],
            '-b:a', preset['audio_bitrate'],
            '-ar', preset['audio_rate']
        ]
    
    @classmethod
    def get_audio_settings(cls, mime_type: str):
        """Get FFmpeg command arguments for audio encoding"""
        if mime_type == 'audio/mpeg':
            return cls.PRESETS['audio']['mp3']['output_flags']
        else:
            preset = cls.PRESETS['audio']['default']
            return [
                '-c:a', preset['codec'],
                '-b:a', preset['bitrate'],
                '-ar', preset['sample_rate']
            ]
    
    @classmethod
    def get_mp3_input_flags(cls):
        """Get FFmpeg input flags specific to MP3 files"""
        return cls.PRESETS['audio']['mp3']['input_flags']