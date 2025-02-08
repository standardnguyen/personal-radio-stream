# media_types.py

from typing import Optional, Dict, List

class MediaTypes:
    """Defines supported media formats and provides type checking functionality"""
    
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
    
    @classmethod
    def get_media_type(cls, mime_type: str) -> Optional[str]:
        """
        Determine if a file is video or audio based on its MIME type
        
        Args:
            mime_type: The MIME type string to check
            
        Returns:
            str: Either 'video' or 'audio' if supported, None if unsupported
        """
        for media_type, formats in cls.SUPPORTED_FORMATS.items():
            if mime_type in formats:
                return media_type
        return None
    
    @classmethod
    def is_supported_format(cls, mime_type: str) -> bool:
        """
        Check if a given MIME type is in our supported formats list
        
        Args:
            mime_type: The MIME type string to check (e.g., 'audio/mp3')
            
        Returns:
            bool: True if the format is supported, False otherwise
        """
        return cls.get_media_type(mime_type) is not None