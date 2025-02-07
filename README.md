# Infinity Stream

A Python-based queue system that uses Trello as a frontend to manage an RTSP media stream. The system automatically processes media files attached to Trello cards and streams them via VLC.

## Quick Start with Docker

1. Create a `.env` file with your credentials:
```bash
TRELLO_API_KEY=your_api_key_here
TRELLO_TOKEN=your_token_here
GITHUB_USERNAME=your_github_username
```

2. Run the container:
```bash
docker-compose up -d
```

## Development Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `config.template.ini` to `config.ini` and fill in your credentials

3. Run the application:
```bash
python start_stream.py
```

## Usage

1. Add a card to the "Queue" list in your Trello board
2. Attach a media file to the card
3. (Optional) Add duration in seconds to the card description
4. The system will automatically:
   - Download the media file
   - Stream it when it reaches the front of the queue
   - Move the card through the lists
   - Clean up old files

## Supported Media Formats

- Video: MP4, MPEG, AVI, MKV, WebM, MOV, FLV
- Audio: MP3, WAV, AAC, OGG, FLAC, M4A

## License

MIT License - See LICENSE file for details