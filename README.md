# Infinity Stream

A Python-based queue system that uses Trello as a frontend to manage media streams. The system automatically processes media files attached to Trello cards and streams them via HTTP Live Streaming (HLS), making it compatible with web browsers and modern streaming infrastructure.

## Quick Start with Docker

For local development and testing, you can run Infinity Stream using Docker Compose:

1. Create a `.env` file with your credentials (use env.example as a reference):
```bash
TRELLO_API_KEY=your_api_key_here
TRELLO_TOKEN=your_token_here
TRELLO_BOARD_NAME=your_board_name
```

2. Run the container:
```bash
docker-compose up -d
```

3. Access your stream at:
```
http://localhost:8080/stream/playlist.m3u8
```

## Development Setup

If you prefer to run the application directly without Docker:

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `config.template.ini` to `config.ini` and fill in your credentials

3. Run the application:
```bash
python start_stream.py
```

## Deployment to DigitalOcean App Platform

### Prerequisites
1. A GitHub account with your fork of this repository
2. A DigitalOcean account
3. Your Trello API credentials (API key and token)

### Deployment Steps

1. Fork this Repository
   - Visit the GitHub repository
   - Click the "Fork" button in the top right
   - Clone your forked repository locally

2. Set Up DigitalOcean App Platform
   - Log into your DigitalOcean account
   - Navigate to "Apps" in the left sidebar
   - Click "Create App"
   - Choose "GitHub" as your source
   - Select your forked repository
   - Choose the branch you want to deploy (usually 'main')

3. Configure Your App
   - Choose "Dockerfile" as your build method
   - Set the following environment variables in the App Platform interface:
     ```
     TRELLO_API_KEY=your_api_key_here
     TRELLO_TOKEN=your_token_here
     TRELLO_BOARD_NAME=your_board_name
     TZ=America/Denver  # Or your preferred timezone
     ```
   - Under "HTTP Port", ensure it's set to 8080

4. Deploy Your App
   - Click "Launch App"
   - Wait for the build and deployment to complete
   - Your stream will be available at:
     ```
     https://your-app-name.ondigitalocean.app/stream/playlist.m3u8
     ```

### Auto-Deploy Configuration

DigitalOcean App Platform automatically rebuilds and deploys your application whenever you push changes to your configured branch. No additional configuration is needed for continuous deployment.

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

The stream is available in HLS format, which is supported by most modern media players and web browsers:

### In a Web Browser
- Direct URL: Access your stream at the provided App Platform URL
- Using VLC: Media > Open Network Stream > Enter the stream URL
- Using any HLS-compatible player (like mpv, ffplay, etc.)

### Stream URLs
- Local Development: `http://localhost:8080/stream/playlist.m3u8`
- Production (DigitalOcean): `https://your-app-name.ondigitalocean.app/stream/playlist.m3u8`

## Supported Media Formats

The system supports a wide range of media formats thanks to FFmpeg:

- Video: MP4, MPEG, AVI, MKV, WebM, MOV, FLV
- Audio: MP3, WAV, AAC, OGG, FLAC, M4A

All formats are automatically converted to HLS format for streaming compatibility.

## Technical Details

The system uses:
- Flask for serving the HLS stream
- FFmpeg for media processing and streaming
- Trello API for queue management
- Python for orchestration
- Docker for containerization

## Troubleshooting

If you encounter issues:

1. Check your environment variables are correctly set in DigitalOcean App Platform
2. Verify your Trello board permissions and API credentials
3. Monitor the application logs in the DigitalOcean dashboard
4. Ensure your media files are in supported formats

For local development issues:
1. Check your .env file configuration
2. Verify Docker is running correctly
3. Check the application logs using `docker-compose logs`

## License

Standard's Petty License
