# Infinity Stream

Infinity Stream is a Python-based media streaming and queue management solution that uses Trello as a control interface. With Infinity Stream, you attach media files to Trello cards and the system automatically downloads, processes, and streams these files over HTTP. Manage your media queue via Trello and control playback using the web interface.

## Features

- **Trello-Driven Queue:** Manage your media queue via Trello cards.
- **Automated Processing:** Downloads and processes media files attached to Trello cards.
- **HTTP Streaming:** Streams media files over HTTP for simple playback via a web interface.
- **Docker-Ready:** Easily deploy using Docker or run locally.

## Quick Start with Docker

For local development and testing, run Infinity Stream using Docker Compose:

1. **Create a `.env` file:**  
   Use `.env.example` as a reference and fill in your credentials:
   ```bash
   TRELLO_API_KEY=your_api_key_here
   TRELLO_TOKEN=your_token_here
   TRELLO_BOARD_NAME=your_board_name
   ```
2. **Start the container:**
   ```bash
   docker-compose up -d
   ```
3. **Access the stream:**  
   Open your browser and navigate to:
   ```
   http://localhost:8080
   ```

## Development Setup

To run the application without Docker:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure the application:**
   - Copy `config.template.ini` to `config.ini` and enter your credentials.
3. **Start the application:**
   ```bash
   python start_stream.py
   ```

## Deployment

### Using DigitalOcean App Platform

1. **Fork and Clone:**  
   Fork the repository on GitHub and clone your fork locally.

2. **Set Up the App:**
   - Log into your DigitalOcean account.
   - Navigate to "Apps" and click "Create App."
   - Connect your GitHub repository and select your deployment branch (usually `main`).

3. **Configure Build Settings:**
   - Choose "Dockerfile" as the build method.
   - Set environment variables in the App Platform dashboard:
     ```
     TRELLO_API_KEY=your_api_key_here
     TRELLO_TOKEN=your_token_here
     TRELLO_BOARD_NAME=your_board_name
     TZ=America/Denver  # Or your preferred timezone
     ```
   - Ensure the HTTP port is set to `8080`.

4. **Deploy Your App:**
   - Click "Launch App" and wait for the deployment to finish.
   - Your application will be available at a URL like:
     ```
     https://your-app-name.ondigitalocean.app
     ```

DigitalOcean App Platform supports automatic deployments on push.

## Usage

1. **Queue Media:**  
   Add a card to the "Queue" list on your Trello board and attach a media file to it.

2. **Automatic Processing:**  
   Infinity Stream downloads, processes, and queues the media file for playback.

3. **Stream Your Media:**  
   Access the web interface at the configured URL (e.g., `http://localhost:8080` or your production URL) to view the media queue and control playback.

## Supported Media Formats

Infinity Stream leverages FFmpeg to support a variety of formats:

- **Video:** MP4, MPEG, AVI, MKV, WebM, MOV, FLV
- **Audio:** MP3, WAV, AAC, OGG, FLAC, M4A

## Technical Overview

- **Backend:** A Flask server handles media processing and streaming.
- **Media Processing:** FFmpeg converts and segments media for HTTP streaming.
- **Queue Management:** The Trello API drives the media queue.
- **Deployment:** Docker simplifies containerization and deployment.

## Troubleshooting

- **Environment Variables:** Ensure your `.env` or platform settings are correct.
- **Trello API:** Verify that your API credentials have the required permissions.
- **Logs:** For Docker, view logs with:
  ```bash
  docker-compose logs
  ```
- **Media Formats:** Confirm that your media files are in a supported format.

## License

Standard's Petty License