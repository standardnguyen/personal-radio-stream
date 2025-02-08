# Infinity Stream

A Python-based queue system that uses Trello as a frontend to manage media streams. The system automatically processes media files attached to Trello cards and streams them via HTTP Live Streaming (HLS), making it compatible with web browsers and modern streaming infrastructure.

## Quick Start with Docker

1. Create a `.env` file with your credentials (use env.example as a reference):
```bash
TRELLO_API_KEY=your_api_key_here
TRELLO_TOKEN=your_token_here
GITHUB_USERNAME=your_github_username
```

2. Run the container:
```bash
docker-compose up -d
```

3. Access your stream at:
```
http://localhost:8080/stream/playlist.m3u8
```

When deployed to DigitalOcean App Platform or similar services, your stream will automatically be available over HTTPS.

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
   - Convert it to HLS format for streaming
   - Stream it when it reaches the front of the queue
   - Move the card through the lists
   - Clean up old files

## Accessing the Stream

The stream is available in HLS format, which is supported by most modern media players and web browsers. You can access it in several ways:

### In a Web Browser
- Direct URL: `http://localhost:8080/stream/playlist.m3u8` (or https:// when deployed)
- Using VLC: Media > Open Network Stream > Enter the stream URL
- Using any HLS-compatible player (like mpv, ffplay, etc.)

### When Deployed
When deployed to platforms like DigitalOcean App Platform, your stream will be available at:
```
https://your-app-name.ondigitalocean.app/stream/playlist.m3u8
```

The platform automatically handles SSL certificates, so you don't need any additional configuration for HTTPS.

## Supported Media Formats

The system supports a wide range of media formats thanks to FFmpeg:

- Video: MP4, MPEG, AVI, MKV, WebM, MOV, FLV
- Audio: MP3, WAV, AAC, OGG, FLAC, M4A

All formats are automatically converted to HLS format for streaming compatibility.

## Deployment

### DigitalOcean App Platform
1. Fork this repository
2. Create a new app in DigitalOcean App Platform
3. Connect it to your forked repository
4. Set your environment variables (TRELLO_API_KEY, TRELLO_TOKEN, etc.)
5. Deploy!

The platform will automatically:
- Build your container
- Provide HTTPS certificates
- Give you a public URL for your stream

## Technical Details

The system uses:
- Flask for serving the HLS stream
- FFmpeg for media processing and streaming
- Trello API for queue management
- Python for orchestration
- Docker for containerization

## License

MIT License - See LICENSE file for details