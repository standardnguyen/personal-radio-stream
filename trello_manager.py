# trello_manager.py

import logging
from typing import List, Optional
from trello import TrelloClient, Board, List as TrelloList
from config_manager import StreamConfig

class TrelloManager:
    """
    Simplified Trello manager that works with just the Queue list
    """

    def __init__(self, config: StreamConfig, logger: logging.Logger):
        """Initialize the Trello manager"""
        self.config = config
        self.logger = logger
        self.client = TrelloClient(
            api_key=config.trello_api_key,
            token=config.trello_token
        )
        self.board: Optional[Board] = None
        self.queue_list: Optional[TrelloList] = None

        # Initialize Trello board and queue list
        self._initialize_trello()

    def _initialize_trello(self) -> None:
        """Initialize Trello board and find the Queue list"""
        try:
            # Test API connection and find board
            boards = list(self.client.list_boards())
            matching_boards = [b for b in boards if b.name == self.config.board_name]

            if not matching_boards:
                raise ValueError(
                    f"Board '{self.config.board_name}' not found. "
                    f"Available boards: {', '.join(b.name for b in boards)}"
                )

            self.board = matching_boards[0]
            self.logger.info(f"Found board: {self.board.name}")

            # Find Queue list
            lists = self.board.list_lists()
            queue_lists = [lst for lst in lists if lst.name == self.config.list_name]

            if not queue_lists:
                # Create Queue list if it doesn't exist
                self.queue_list = self.board.add_list(self.config.list_name)
                self.logger.info(f"Created new Queue list")
            else:
                self.queue_list = queue_lists[0]
                self.logger.info(f"Found existing Queue list")

        except Exception as e:
            self.logger.error(f"Failed to initialize Trello: {str(e)}")
            raise

    def get_queue_cards(self) -> List:
        """Get all cards in the Queue list"""
        return self.queue_list.list_cards()

    def get_card_attachments(self, card) -> List:
        """Get all attachments for a card"""
        return card.get_attachments()
