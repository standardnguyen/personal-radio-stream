# player_template.py

from pathlib import Path
import logging

class PlayerTemplate:
    """
    Manages the HTML5 player template for HLS streaming with enhanced error handling,
    debugging capabilities, and automatic reloading for continuous playback.
    """

    # HTML template for the web player with HLS.js configuration and auto-reload functionality
    TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Player</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.4.12/hls.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: system-ui, -apple-system, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .player-wrapper {
            width: 100%;
            margin: 20px 0;
            position: relative;
        }
        #videoPlayer {
            width: 100%;
            background: #000;
            border-radius: 4px;
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            background: #e8f5e9;
            color: #2e7d32;
        }
        .error {
            background: #ffebee;
            color: #c62828;
        }
        .warning {
            background: #fff3e0;
            color: #ef6c00;
        }
        .debug-panel {
            margin-top: 20px;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            display: none;
        }
        .debug-panel.show {
            display: block;
        }
        #debugLog {
            max-height: 200px;
            overflow-y: auto;
            margin-top: 10px;
        }
        .debug-line {
            margin: 2px 0;
            padding: 2px 4px;
        }
        .debug-line.error { color: #c62828; }
        .debug-line.warning { color: #ef6c00; }
        .debug-line.info { color: #1565c0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Stream Player</h1>
        <div class="player-wrapper">
            <video id="videoPlayer" controls></video>
        </div>
        <div id="status" class="status">Initializing player...</div>
        <div class="debug-panel" id="debugPanel">
            <h3>Debug Information</h3>
            <div><strong>HLS.js Version:</strong> <span id="hlsVersion"></span></div>
            <div><strong>Stream URL:</strong> <span id="streamUrl"></span></div>
            <div><strong>Player State:</strong> <span id="playerState">Initializing</span></div>
            <div id="debugLog"></div>
        </div>
    </div>
    <script>
        const video = document.getElementById('videoPlayer');
        const status = document.getElementById('status');
        const debugPanel = document.getElementById('debugPanel');
        const debugLog = document.getElementById('debugLog');
        const streamUrl = '/stream/playlist.m3u8';

        // Debug logging function
        function log(level, message) {
            const line = document.createElement('div');
            line.className = `debug-line ${level}`;
            line.textContent = `${new Date().toISOString().split('T')[1]} [${level}] ${message}`;
            debugLog.appendChild(line);
            debugLog.scrollTop = debugLog.scrollHeight;
            console.log(`[${level}] ${message}`);
        }

        // Display HLS.js version and stream URL in the debug panel
        document.getElementById('hlsVersion').textContent = Hls.version;
        document.getElementById('streamUrl').textContent = streamUrl;

        // Enable toggling of the debug panel with Ctrl+D
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'd') {
                debugPanel.classList.toggle('show');
            }
        });

        function initPlayer() {
            if (Hls.isSupported()) {
                const hls = new Hls({
                    debug: true,
                    enableWorker: true,
                    lowLatencyMode: true,
                    backBufferLength: 90,
                    maxBufferLength: 30,
                    maxMaxBufferLength: 600,
                    maxBufferSize: 60 * 1000 * 1000,
                    maxBufferHole: 0.5,
                    manifestLoadingTimeOut: 10000,
                    manifestLoadingMaxRetry: 4,
                    levelLoadingTimeOut: 10000,
                    levelLoadingMaxRetry: 4,
                    fragLoadingTimeOut: 20000,
                    fragLoadingMaxRetry: 6
                });

                // When the manifest is parsed, start playback
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    log('info', 'Manifest parsed successfully');
                    status.textContent = 'Stream ready - Playing...';
                    document.getElementById('playerState').textContent = 'Playing';
                    video.play().catch(e => {
                        status.textContent = 'Click play to start streaming';
                        log('warning', `Autoplay failed: ${e.message}`);
                    });
                });

                // Error handling with auto-reload for fatal errors
                hls.on(Hls.Events.ERROR, (event, data) => {
                    if(data.fatal) {
                        log('error', `Fatal error: ${data.type} - ${data.details}`);
                        status.className = 'status error';
                        status.textContent = 'Stream error - Attempting to recover...';
                        document.getElementById('playerState').textContent = 'Error';
                        switch(data.type) {
                            case Hls.ErrorTypes.NETWORK_ERROR:
                                log('info', 'Attempting to recover from network error');
                                hls.startLoad();
                                break;
                            case Hls.ErrorTypes.MEDIA_ERROR:
                                log('info', 'Attempting to recover from media error');
                                hls.recoverMediaError();
                                break;
                            default:
                                log('error', 'Unrecoverable error - Reloading stream');
                                reloadStream(hls);
                                break;
                        }
                    } else {
                        log('warning', `Non-fatal error: ${data.type} - ${data.details}`);
                    }
                });

                // If playback ends, reload the stream
                video.addEventListener('ended', () => {
                    log('info', 'Playback ended, reloading stream');
                    reloadStream(hls);
                });

                // Function to reload the stream by detaching and reattaching the source
                function reloadStream(hlsInstance) {
                    hlsInstance.detachMedia();
                    video.pause();
                    video.src = "";
                    setTimeout(() => {
                        hlsInstance.loadSource(streamUrl);
                        hlsInstance.attachMedia(video);
                        video.play().catch(e => log('warning', `Autoplay failed: ${e.message}`));
                    }, 1000); // Delay to allow the backend to generate new segments
                }

                hls.loadSource(streamUrl);
                hls.attachMedia(video);
                log('info', 'HLS player initialized');
            }
            else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                log('info', 'Using native HLS playback');
                video.src = streamUrl;
                video.addEventListener('loadedmetadata', () => {
                    status.textContent = 'Stream ready - Playing...';
                    document.getElementById('playerState').textContent = 'Playing';
                    video.play().catch(e => {
                        status.textContent = 'Click play to start streaming';
                        log('warning', `Autoplay failed: ${e.message}`);
                    });
                });
                video.addEventListener('error', (e) => {
                    const error = video.error;
                    log('error', `Playback error: ${error.message}`);
                    status.className = 'status error';
                    status.textContent = 'Playback error - Please try refreshing';
                    document.getElementById('playerState').textContent = 'Error';
                });
            }
            else {
                log('error', 'HLS playback not supported');
                status.className = 'status error';
                status.textContent = 'Your browser does not support HLS playback';
                document.getElementById('playerState').textContent = 'Unsupported';
            }
        }

        // Log any uncaught errors
        window.addEventListener('error', (e) => {
            log('error', `Uncaught error: ${e.message}`);
        });

        initPlayer();
    </script>
</body>
</html>'''

    @classmethod
    def create_player_page(cls, hls_dir: Path, logger: logging.Logger) -> None:
        """
        Create the HTML5 player page with HLS.js support and debugging capabilities.

        Args:
            hls_dir: Directory where the player.html file will be created.
            logger: Logger instance for logging debug/info messages.
        """
        try:
            player_path = hls_dir / 'player.html'
            logger.info(f"Creating player page at: {player_path}")

            with open(player_path, 'w') as f:
                f.write(cls.TEMPLATE)

            logger.info("Player page created successfully")
        except Exception as e:
            logger.error(f"Error creating player page: {str(e)}")
            raise
