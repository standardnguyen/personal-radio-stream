# player_template.py

from pathlib import Path

class PlayerTemplate:
    """Manages the HTML5 player template for HLS streaming"""
    
    # HTML template for the web player with HLS.js
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
    </style>
</head>
<body>
    <div class="container">
        <h1>Stream Player</h1>
        <div class="player-wrapper">
            <video id="videoPlayer" controls></video>
        </div>
        <div id="status" class="status">Connecting to stream...</div>
    </div>

    <script>
        const video = document.getElementById('videoPlayer');
        const status = document.getElementById('status');
        const streamUrl = '/stream/playlist.m3u8';

        function initPlayer() {
            if (Hls.isSupported()) {
                const hls = new Hls({
                    debug: false,
                    enableWorker: true,
                    lowLatencyMode: true,
                    backBufferLength: 90
                });
                
                hls.loadSource(streamUrl);
                hls.attachMedia(video);
                
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    status.textContent = 'Stream ready - Playing...';
                    video.play().catch(e => {
                        status.textContent = 'Click play to start streaming';
                    });
                });

                hls.on(Hls.Events.ERROR, (event, data) => {
                    if (data.fatal) {
                        status.className = 'status error';
                        status.textContent = 'Stream error - Reconnecting...';
                        setTimeout(() => hls.loadSource(streamUrl), 2000);
                    }
                });
            }
            else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = streamUrl;
                video.addEventListener('loadedmetadata', () => {
                    status.textContent = 'Stream ready - Playing...';
                    video.play().catch(e => {
                        status.textContent = 'Click play to start streaming';
                    });
                });
            }
            else {
                status.className = 'status error';
                status.textContent = 'Your browser does not support HLS playback';
            }
        }

        initPlayer();
    </script>
</body>
</html>'''

    @classmethod
    def create_player_page(cls, hls_dir: Path) -> None:
        """
        Create the HTML5 player page with HLS.js support
        
        Args:
            hls_dir: Directory where the player.html should be created
        """
        player_path = hls_dir / 'player.html'
        with open(player_path, 'w') as f:
            f.write(cls.TEMPLATE)