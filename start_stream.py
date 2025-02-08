from stream_processor import StreamQueueProcessor
import configparser

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Initialize the processor
processor = StreamQueueProcessor(
    trello_api_key=config['Trello']['api_key'],
    trello_token=config['Trello']['token'],
    board_name=config['Trello']['board_name'],
    list_name=config['Trello']['list_name'],
    media_dir=config['Storage'].get('media_dir', 'downloaded_media'),
    cleanup_interval_hours=int(config['Storage'].get('cleanup_hours', '24')),
    max_storage_mb=int(config['Storage'].get('max_storage_mb', '5000')),
    stream_port=int(config['Stream'].get('port', '8080'))  # Now using HTTP port instead of RTSP URL
)

try:
    print("Starting stream processor...")
    processor.start()
    
    print("\nProcessor is running! Press Ctrl+C to stop.")
    print("To use:")
    print("1. Add a card to the 'Queue' list in your Trello board")
    print("2. Attach a media file to the card")
    print("3. (Optional) Add duration in seconds in the card description")
    print(f"\nStream will be available at: http://localhost:{config['Stream'].get('port', '8080')}/stream/playlist.m3u8")
    
    while True:
        input()  # Keep the script running until Ctrl+C
        
except KeyboardInterrupt:
    print("\nStopping stream processor...")
    processor.stop()
    print("Processor stopped successfully.")