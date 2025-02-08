# queue_processor.py

import time
import logging
from threading import Thread, Event
from pathlib import Path
from typing import Optional, Dict
from collections import deque
from datetime import datetime

class QueueProcessor:
    """
    Handles the processing of media queue from Trello cards.
    Implements a robust queue system with proper state management.
    """
    
    def __init__(
        self,
        trello,
        media,
        cleanup_interval: int,
        logger: logging.Logger
    ):
        """
        Initialize the queue processor with improved state management
        
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
        
        # Improved state management
        self.is_running = False
        self.last_cleanup = time.time()
        self.process_thread: Optional[Thread] = None
        self.current_card = None
        self.queue = deque()  # Thread-safe queue for card processing
        self.card_states: Dict = {}  # Track card processing states
        self.stop_event = Event()  # For graceful shutdown
        
    def start(self) -> None:
        """Start the queue processing thread with improved error handling"""
        if not self.is_running:
            self.is_running = True
            self.stop_event.clear()
            self.process_thread = Thread(target=self._process_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            self.logger.info("Queue processor started")
    
    def stop(self) -> None:
        """Stop the queue processor gracefully"""
        self.logger.info("Stopping queue processor...")
        self.is_running = False
        self.stop_event.set()
        
        # Stop current media playback
        self.media.stop_stream()
        
        if self.process_thread:
            self.process_thread.join(timeout=5)
            
        # Move any processing cards back to queue
        if self.current_card:
            try:
                self.trello.move_card_to_list(self.current_card, 'Queue')
            except Exception as e:
                self.logger.error(f"Error returning card to queue: {str(e)}")
    
    def _update_queue(self) -> None:
        """Update the internal queue with cards from Trello"""
        try:
            queue_cards = self.trello.get_queue_cards()
            
            # Add new cards to queue
            for card in queue_cards:
                if card.id not in self.card_states:
                    self.card_states[card.id] = {
                        'status': 'queued',
                        'attempts': 0,
                        'last_attempt': None
                    }
                    self.queue.append(card)
                    self.logger.info(f"Added card to queue: {card.name}")
                    
        except Exception as e:
            self.logger.error(f"Error updating queue: {str(e)}")
    
    def _process_card(self, card) -> bool:
        """
        Process a single card with improved error handling
        
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            # Update card state
            self.card_states[card.id]['status'] = 'processing'
            self.card_states[card.id]['attempts'] += 1
            self.card_states[card.id]['last_attempt'] = datetime.now()
            
            # Move card to Now Playing
            self.trello.move_card_to_list(card, 'Now Playing')
            self.current_card = card
            
            # Get and validate attachment
            attachments = self.trello.get_card_attachments(card)
            if not attachments:
                self.logger.warning(f"No attachments found on card: {card.name}")
                return False
            
            # Download and process attachment
            media_path = self.media.download_attachment(attachments[0])
            if not media_path:
                return False
            
            # Get duration from card description
            try:
                duration = int(card.description) if card.description.strip().isdigit() else None
            except (AttributeError, ValueError):
                duration = None
            
            # Stream media without blocking the queue processor
            self.media.stream_media(media_path, duration, wait_for_completion=False)
            
            # Monitor playback completion
            while self.media.current_media == media_path and not self.stop_event.is_set():
                time.sleep(1)
            
            # Mark card as completed if we didn't stop early
            if not self.stop_event.is_set():
                self.trello.move_card_to_list(card, 'Played')
                self.card_states[card.id]['status'] = 'completed'
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error processing card {card.name}: {str(e)}")
            return False
            
        finally:
            self.current_card = None
    
    def _process_queue(self) -> None:
        """Main queue processing loop with improved state management"""
        while self.is_running:
            try:
                # Update queue from Trello
                self._update_queue()
                
                # Process next card if available
                if self.queue and not self.current_card:
                    card = self.queue.popleft()
                    
                    # Check if we should retry this card
                    state = self.card_states[card.id]
                    if state['attempts'] >= 3:
                        self.logger.warning(f"Card {card.name} failed after 3 attempts")
                        self.trello.move_card_to_list(card, 'Played')
                        continue
                    
                    # Process the card
                    success = self._process_card(card)
                    if not success and not self.stop_event.is_set():
                        # Return card to queue for retry
                        self.queue.append(card)
                
                # Run cleanup if needed
                if time.time() - self.last_cleanup > self.cleanup_interval:
                    self.media.cleanup_media()
                    self.last_cleanup = time.time()
                
                # Short sleep to prevent busy waiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in queue processing loop: {str(e)}")
                time.sleep(5)  # Longer sleep on error to prevent rapid retries