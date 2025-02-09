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
        """Main processing loop - cycle through all cards in the Queue list."""
        while self.is_running:
            try:
                # Retrieve all cards in the Queue list
                queue_cards = self.trello.get_queue_cards()

                if queue_cards:
                    # Loop through each card in the queue
                    for card in queue_cards:
                        attachments = self.trello.get_card_attachments(card)
                        if attachments:
                            # Download and validate the first attachment
                            media_path = self.media.download_attachment(attachments[0])
                            if media_path:
                                # Try to get an optional duration from the card description
                                try:
                                    duration = int(card.description.strip()) if card.description and card.description.strip().isdigit() else None
                                except (AttributeError, ValueError):
                                    duration = None

                                self.logger.info(f"Playing: {card.name}")
                                self.media.stream_media(media_path, duration)
                                self.logger.info(f"Finished playing: {card.name}")
                            else:
                                self.logger.warning(f"Failed to download media for card: {card.name}")
                        else:
                            self.logger.warning(f"No attachments found on card: {card.name}")

                        # (Optional) Add a short delay between processing individual cards
                        time.sleep(1)
                else:
                    self.logger.info("No cards in queue")

                # Run cleanup if needed based on the configured cleanup interval
                if time.time() - self.last_cleanup > self.cleanup_interval:
                    self.media.cleanup_media()
                    self.last_cleanup = time.time()

                # Sleep a bit before checking the queue again
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in queue processing loop: {str(e)}")
                time.sleep(5)  # Longer sleep on error
