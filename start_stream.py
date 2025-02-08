# start_stream.py

from stream_processor import StreamQueueProcessor
import configparser
import logging
import sys
import os

def load_config():
    """
    Load and validate configuration from config.ini
    
    Returns:
        configparser.ConfigParser: Parsed configuration object
        
    Raises:
        ValueError: If required sections are missing
    """
    try:
        logger.info("Loading configuration...")
        
        # Load configuration file
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Validate required sections
        required_sections = ['Trello', 'Storage', 'Stream']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required section '{section}' in config.ini")
        
        return config
        
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise

def main():
    """
    Main entry point for the stream processor application.
    Handles configuration loading, processor initialization, and shutdown.
    """
    try:
        # Set up logging
        global logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('startup.log')
            ]
        )
        logger = logging.getLogger(__name__)
        
        # Load configuration
        config = load_config()
        
        # Initialize the processor
        logger.info("Initializing StreamQueueProcessor...")
        processor = StreamQueueProcessor(
            trello_api_key=config['Trello']['api_key'],
            trello_token=config['Trello']['token'],
            board_name=config['Trello']['board_name'],
            list_name=config['Trello']['list_name'],
            media_dir=config['Storage'].get('media_dir', 'downloaded_media'),
            cleanup_interval_hours=int(config['Storage'].get('cleanup_hours', '24')),
            max_storage_mb=int(config['Storage'].get('max_storage_mb', '5000')),
            stream_port=int(config['Stream'].get('port', '8080'))
        )
        
        # Start the processor
        logger.info("Starting stream processor...")
        processor.start()
        
        # Display usage information
        logger.info("\nProcessor is running! Press Ctrl+C to stop.")
        logger.info("\nTo use:")
        logger.info("1. Add a card to the 'Queue' list in your Trello board")
        logger.info("2. Attach a media file to the card")
        logger.info("3. (Optional) Add duration in seconds in the card description")
        logger.info(f"\nStream will be available at: http://localhost:{config['Stream'].get('port', '8080')}/stream/playlist.m3u8")
        
        # Keep the script running
        while True:
            input()
            
    except KeyboardInterrupt:
        logger.info("\nStopping stream processor...")
        processor.stop()
        logger.info("Processor stopped successfully.")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()