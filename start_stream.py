import sys
import os
import configparser
import logging
from pathlib import Path
from web_server import StreamServer
from trello_manager import TrelloManager
from config_manager import StreamConfig, LoggerSetup

def main():
    # Set up logging
    logger = LoggerSetup.setup_logger('StreamProcessor', 'startup.log')
    
    try:
        # Load configuration from environment variables
        config = StreamConfig(
            trello_api_key=os.getenv('TRELLO_API_KEY'),
            trello_token=os.getenv('TRELLO_TOKEN'),
            board_name=os.getenv('TRELLO_BOARD_NAME'),
            list_name='Queue',
            media_dir=Path('downloaded_media'),
            cleanup_interval_hours=24,
            max_storage_mb=5000,
            stream_port=8080
        )
        
        # Initialize Trello manager
        trello = TrelloManager(config, logger)
        
        # Start web server
        server = StreamServer(config.media_dir, logger, trello)
        server.run(port=config.stream_port)
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()