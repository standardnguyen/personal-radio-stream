# trello_manager.py

import logging
from typing import Dict, List, Optional
from trello import TrelloClient, Board, List as TrelloList
from config_manager import StreamConfig

class TrelloManager:
    """Manages all Trello-related operations for the stream processor"""
    
    def __init__(self, config: StreamConfig, logger: logging.Logger):
        """
        Initialize the Trello manager with configuration
        
        Args:
            config: StreamConfig instance containing Trello credentials
            logger: Configured logger instance
        """
        self.config = config
        self.logger = logger
        self.client = TrelloClient(
            api_key=config.trello_api_key,
            token=config.trello_token
        )
        self.board: Optional[Board] = None
        self.lists: Dict[str, TrelloList] = {}
        
        # Initialize Trello board and lists
        self._initialize_trello()
    
    def _initialize_trello(self) -> None:
        """
        Initialize Trello board and create required lists if they don't exist
        
        Raises:
            ValueError: If the specified board is not found
        """
        try:
            # Test API connection
            boards = list(self.client.list_boards())
            board_names = [board.name for board in boards]
            self.logger.info(f"Connected to Trello. Found {len(boards)} boards")
            
            # Find specified board
            matching_boards = [b for b in boards if b.name == self.config.board_name]
            if not matching_boards:
                raise ValueError(
                    f"Board '{self.config.board_name}' not found. "
                    f"Available boards: {', '.join(board_names)}"
                )
            
            self.board = matching_boards[0]
            self.logger.info(f"Found board: {self.board.name} (ID: {self.board.id})")
            
            # Set up required lists
            self._setup_lists()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Trello: {str(e)}")
            raise
    
    def _setup_lists(self) -> None:
        """Create or find required Trello lists"""
        list_names = ['Queue', 'Now Playing', 'Played']
        existing_lists = {lst.name: lst for lst in self.board.list_lists()}
        
        for name in list_names:
            if name in existing_lists:
                self.lists[name] = existing_lists[name]
                self.logger.info(f"Using existing list: {name}")
            else:
                self.lists[name] = self.board.add_list(name)
                self.logger.info(f"Created new list: {name}")
    
    def get_queue_cards(self) -> List:
        """Return all cards in the Queue list"""
        return self.lists['Queue'].list_cards()
    
    def move_card_to_list(self, card, list_name: str) -> None:
        """
        Move a card to the specified list
        
        Args:
            card: Trello card object
            list_name: Name of the destination list
        """
        if list_name in self.lists:
            card.change_list(self.lists[list_name].id)
            self.logger.info(f"Moved card '{card.name}' to '{list_name}'")
        else:
            self.logger.error(f"List '{list_name}' not found")
    
    def get_card_attachments(self, card) -> List:
        """
        Get all attachments for a card
        
        Args:
            card: Trello card object
            
        Returns:
            List of attachment objects
        """
        return card.get_attachments()