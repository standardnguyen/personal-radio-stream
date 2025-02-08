# queue_processor.py

import time
import logging
from threading import Thread
from pathlib import Path
from typing import Optional
from trello_manager import TrelloManager
from media_manager import MediaManager

class QueueProcessor:
    """
    Handles the processing of media queue from Trello cards.
    Responsible for monitoring the queue and coordinating media playback.
    """
    
    def __init__(
        self,
        trello: TrelloManager,
        media: MediaManager,
        cleanup_interval: int,
        logger: logging.Logger
    ):
        """
        Initialize the queue processor
        
        Args:
            trello: TrelloManager instance for queue management
            media: MediaManager instance for media handling
            cleanup_interval: Time between cleanup runs in seconds
            logger: Logger instance for logging
        """
        self.trello = trello
        self.media = media
        self.cleanup_interval = cleanup_interval
        self.logger = logger
        self.is_running = False
        self.last_cleanup = time.time()
        self.process_thread: Optional[Thread] = None
    
    def start(self) -> None:
        """Start the queue processing thread"""
        self.is_running = True
        self.process_thread = Thread(target=self._process_queue)
        self.process_thread.daemon = True
        self.process_thread.start()
    
    def stop(self) -> None:
        """Stop the queue processor"""
        self.is_running = False
        if self.process_thread:
            self.process_thread.join(timeout=5)
    
    def _process_queue(self) -> None:
        """Main queue processing loop"""
        while self.is_running:
            try:
                # Get all cards from Queue list
                queue_cards = self.trello.get_queue_cards()
                
                if queue_cards:
                    for card in queue_cards:
                        self.logger.info(f"Processing card: {card.name}")
                        
                        # Move card to Now Playing
                        self.trello.move_card_to_list(card, 'Now Playing')
                        
                        # Get media attachment
                        attachments = self.trello.get_card_attachments(card)
                        if not attachments:
                            self.logger.warning(f"No attachments found on card: {card.name}")
                            self.trello.move_card_to_list(card, 'Played')
                            continue
                        
                        # Download and validate the first attachment
                        attachment = attachments[0]
                        media_path = self.media.download_attachment(attachment)
                        
                        if not media_path:
                            self.logger.error(f"Failed to download attachment from card: {card.name}")
                            self.trello.move_card_to_list(card, 'Played')
                            continue
                        
                        # Get duration from card description if available
                        try:
                            duration = int(card.description) if card.description.strip().isdigit() else None
                        except (AttributeError, ValueError):
                            duration = None
                        
                        # Stream the media with continuous playback
                        self.media.stream_media(media_path, duration, wait_for_completion=True)
                        
                        # Move card to Played list after completion
                        self.trello.move_card_to_list(card, 'Played')
                        
                        # Check if cleanup is needed
                        if time.time() - self.last_cleanup > self.cleanup_interval:
                            self.media.cleanup_media()
                            self.last_cleanup = time.time()
                
                time.sleep(5)  # Prevent excessive API calls
                
            except Exception as e:
                self.logger.error(f"Error in queue processing: {str(e)}")
                time.sleep(30)  # Wait longer on error