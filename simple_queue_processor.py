# simple_queue_processor.py

import time
import logging
from threading import Thread, Event
from pathlib import Path
from typing import Optional

class SimpleQueueProcessor:
    """
    A simplified queue processor that plays cards from the Queue list.
    Cards remain in the Queue list after playing, allowing for repeated playback.
    """

    def __init__(
        self,
        trello,
        media,
        cleanup_interval: int,
        logger: logging.Logger
    ):
        self.trello = trello
        self.media = media
        self.cleanup_interval = cleanup_interval
        self.logger = logger

        self.is_running = False
        self.last_cleanup = time.time()
        self.process_thread: Optional[Thread] = None
        self.stop_event = Event()

    def start(self) -> None:
        """Start processing the queue"""
        if not self.is_running:
            self.is_running = True
            self.stop_event.clear()
            self.process_thread = Thread(target=self._process_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            self.logger.info("Queue processor started")

    def stop(self) -> None:
        """Stop the processor"""
        self.logger.info("Stopping queue processor...")
        self.is_running = False
        self.stop_event.set()
        self.media.stop_stream()

        if self.process_thread:
            self.process_thread.join(timeout=5)

    def _process_queue(self) -> None:
        """Main processing loop - play what's in the Queue list and keep cards there"""
        while self.is_running:
            try:
                # Get all cards in Queue
                queue_cards = self.trello.get_queue_cards()

                # Process next card if we have one
                if queue_cards:
                    card = queue_cards[0]  # Get first card

                    # Get and validate attachment
                    attachments = self.trello.get_card_attachments(card)
                    if attachments:
                        # Download and process attachment
                        media_path = self.media.download_attachment(attachments[0])
                        if media_path:
                            # Get optional duration
                            try:
                                duration = int(card.description) if card.description.strip().isdigit() else None
                            except (AttributeError, ValueError):
                                duration = None

                            # Play the media and wait for completion
                            self.logger.info(f"Playing: {card.name}")
                            self.media.stream_media(media_path, duration)

                            # After playing, log completion but don't archive
                            self.logger.info(f"Finished playing: {card.name}")
                    else:
                        self.logger.warning(f"No attachments found on card: {card.name}")

                # Run cleanup if needed
                if time.time() - self.last_cleanup > self.cleanup_interval:
                    self.media.cleanup_media()
                    self.last_cleanup = time.time()

                # Short sleep to prevent busy waiting
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in queue processing loop: {str(e)}")
                time.sleep(5)  # Longer sleep on error
