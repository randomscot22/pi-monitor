#!/usr/bin/env python3
"""
HDMI Capture Stream Server
Streams from a v4l2 capture device over HTTP as HLS or MJPEG.
Access the web UI from any browser on your network.

Usage:
    python3 stream_server.py [options]

Options:
    --device    Video device (default: /dev/video0)
    --width     Capture width (default: 1920)
    --height    Capture height (default: 1080)
    --port      HTTP port (default: 8080)
    --mode      Stream mode: hls or mjpeg (default: hls)
    --bitrate   HLS bitrate in kbps (default: 2000)
    --hwenc     Use hardware H264 encoder (h264_v4l2m2m) for Pi 4/5
"""

import argparse
import http.server
import io
import logging
import os
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stream-server")

# ── HTML page served to the browser ──────────────────────────────────────────

PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HDMI Stream</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0a0c0f;
    --surface: #111418;
    --border: #1e2530;
    --accent: #00e5ff;
    --accent2: #ff3d71;
    --text: #c8d6e5;
    --muted: #4a5568;
    --mono: 'Share Tech Mono', monospace;
    --sans: 'Barlow', sans-serif;
  }

  html, body {
    height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-weight: 300;
    overflow-x: hidden;
  }

  /* Scanline overlay */
  body::after {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,0.08) 2px,
      rgba(0,0,0,0.08) 4px
    );
    pointer-events: none;
    z-index: 999;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .logo {
    font-family: var(--mono);
    font-size: 13px;
    letter-spacing: 0.15em;
    color: var(--accent);
    text-transform: uppercase;
  }

  .logo span { color: var(--accent2); }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--muted);
    text-transform: uppercase;
  }

  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--muted);
    transition: background 0.4s;
  }
  .dot.live { background: var(--accent2); box-shadow: 0 0 8px var(--accent2); animation: pulse 1.5s infinite; }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  main {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 32px 20px 48px;
    gap: 24px;
    min-height: calc(100vh - 57px);
  }

  .player-wrap {
    position: relative;
    width: 100%;
    max-width: 1100px;
    background: #000;
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
    box-shadow: 0 0 60px rgba(0,229,255,0.04), 0 20px 60px rgba(0,0,0,0.6);
  }

  .player-wrap::before {
    content: '';
    display: block;
    padding-top: 56.25%; /* 16:9 */
  }

  video, #mjpeg-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    background: #000;
  }

  .overlay-msg {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    font-family: var(--mono);
    font-size: 13px;
    color: var(--muted);
    letter-spacing: 0.1em;
  }

  .spinner {
    width: 32px; height: 32px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .info-bar {
    width: 100%;
    max-width: 1100px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1px;
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
    font-family: var(--mono);
    font-size: 11px;
  }

  .info-cell {
    background: var(--surface);
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .info-cell .label { color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; }
  .info-cell .value { color: var(--accent); font-size: 13px; }

  .controls {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: center;
  }

  button {
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 9px 20px;
    border-radius: 3px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    transition: border-color 0.2s, color 0.2s, box-shadow 0.2s;
  }

  button:hover { border-color: var(--accent); color: var(--accent); box-shadow: 0 0 12px rgba(0,229,255,0.1); }
  button.danger:hover { border-color: var(--accent2); color: var(--accent2); box-shadow: 0 0 12px rgba(255,61,113,0.1); }
</style>
</head>
<body>

<header>
  <div class="logo">HDMI<span>//</span>Stream</div>
  <div class="status-pill">
    <div class="dot" id="live-dot"></div>
    <span id="live-label">Connecting…</span>
  </div>
</header>

<main>
  <div class="player-wrap" id="player-wrap">
    <!-- filled by JS -->
    <div class="overlay-msg" id="overlay">
      <div class="spinner"></div>
      <span>Waiting for stream…</span>
    </div>
  </div>

  <div class="info-bar">
    <div class="info-cell">
      <span class="label">Device</span>
      <span class="value" id="info-device">—</span>
    </div>
    <div class="info-cell">
      <span class="label">Resolution</span>
      <span class="value" id="info-res">—</span>
    </div>
    <div class="info-cell">
      <span class="label">Mode</span>
      <span class="value" id="info-mode">—</span>
    </div>
    <div class="info-cell">
      <span class="label">Uptime</span>
      <span class="value" id="info-uptime">—</span>
    </div>
  </div>

  <div class="controls">
    <button onclick="toggleFullscreen()">⛶ Fullscreen</button>
    <button onclick="location.reload()">↺ Reconnect</button>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
const MODE    = "{{MODE}}";
const DEVICE  = "{{DEVICE}}";
const WIDTH   = "{{WIDTH}}";
const HEIGHT  = "{{HEIGHT}}";

document.getElementById('info-device').textContent = DEVICE;
document.getElementById('info-res').textContent    = WIDTH + ' × ' + HEIGHT;
document.getElementById('info-mode').textContent   = MODE.toUpperCase();

// Uptime counter
let seconds = 0;
setInterval(() => {
  seconds++;
  const h = String(Math.floor(seconds/3600)).padStart(2,'0');
  const m = String(Math.floor((seconds%3600)/60)).padStart(2,'0');
  const s = String(seconds%60).padStart(2,'0');
  document.getElementById('info-uptime').textContent = `${h}:${m}:${s}`;
}, 1000);

function setLive(live) {
  const dot   = document.getElementById('live-dot');
  const label = document.getElementById('live-label');
  dot.className   = 'dot' + (live ? ' live' : '');
  label.textContent = live ? 'Live' : 'Buffering…';
}

const wrap    = document.getElementById('player-wrap');
const overlay = document.getElementById('overlay');

function hideOverlay() { overlay.style.display = 'none'; }

if (MODE === 'mjpeg') {
  const img = document.createElement('img');
  img.id = 'mjpeg-img';
  img.src = '/stream.mjpeg';
  img.onload = () => { hideOverlay(); setLive(true); };
  img.onerror = () => setLive(false);
  wrap.appendChild(img);
} else {
  // HLS
  const video = document.createElement('video');
  video.autoplay = true;
  video.muted    = true;
  video.controls = true;
  video.style.position = 'absolute';
  video.style.inset = '0';
  video.style.width = '100%';
  video.style.height = '100%';
  video.style.background = '#000';
  wrap.appendChild(video);

  function loadHLS() {
    if (Hls.isSupported()) {
      const hls = new Hls({ lowLatencyMode: true, liveSyncDurationCount: 2 });
      hls.loadSource('/stream/stream.m3u8');
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => { video.play(); hideOverlay(); setLive(true); });
      hls.on(Hls.Events.ERROR, (_, d) => { if (d.fatal) { setLive(false); setTimeout(loadHLS, 3000); } });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = '/stream/stream.m3u8';
      video.addEventListener('loadedmetadata', () => { video.play(); hideOverlay(); setLive(true); });
    }
  }
  loadHLS();
}

function toggleFullscreen() {
  if (!document.fullscreenElement) wrap.requestFullscreen();
  else document.exitFullscreen();
}
</script>
</body>
</html>
"""

# ── MJPEG frame broadcaster ───────────────────────────────────────────────────

class MJPEGBroadcaster:
    """Reads JPEG frames from FFmpeg stdout and fans them out to connected clients."""

    BOUNDARY = b"--mjpegframe"

    def __init__(self):
        self.clients: list[queue.Queue] = []
        self.lock = threading.Lock()
        self.ffmpeg: subprocess.Popen | None = None

    def add_client(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=4)
        with self.lock:
            self.clients.append(q)
        log.info("MJPEG client connected (total: %d)", len(self.clients))
        return q

    def remove_client(self, q: queue.Queue):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)
        log.info("MJPEG client disconnected (total: %d)", len(self.clients))

    def broadcast(self, frame: bytes):
        header = (
            self.BOUNDARY + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
        )
        chunk = header + frame + b"\r\n"
        with self.lock:
            dead = []
            for q in self.clients:
                try:
                    q.put_nowait(chunk)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self.clients.remove(q)

    def run(self, device: str, width: int, height: int, fps: int):
        cmd = [
            "ffmpeg", "-loglevel", "error",
            "-f", "v4l2",
            "-framerate", str(fps),      # tell v4l2 the input rate
            "-video_size", f"{width}x{height}",
            "-pixel_format", "bgr24",
            "-i", device,
            "-c:v", "mjpeg",
            "-q:v", "5",
            "-r", str(fps),              # force output rate
            "-f", "mjpeg",
            "pipe:1",
        ]
        log.info("Starting FFmpeg MJPEG: %s", " ".join(cmd))
        self.ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        buf = b""
        SOI = b"\xff\xd8"
        EOI = b"\xff\xd9"

        while True:
            chunk = self.ffmpeg.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                start = buf.find(SOI)
                if start == -1:
                    buf = b""
                    break
                end = buf.find(EOI, start + 2)
                if end == -1:
                    buf = buf[start:]
                    break
                frame = buf[start:end + 2]
                buf = buf[end + 2:]
                self.broadcast(frame)

        log.warning("FFmpeg MJPEG process ended")

    def stop(self):
        if self.ffmpeg:
            self.ffmpeg.terminate()


# ── HLS via FFmpeg ────────────────────────────────────────────────────────────

class HLSStreamer:
    def __init__(self, stream_dir: Path):
        self.stream_dir = stream_dir
        self.ffmpeg: subprocess.Popen | None = None

    def run(self, device: str, width: int, height: int, bitrate: int, hwenc: bool, fps: int):
        self.stream_dir.mkdir(parents=True, exist_ok=True)
        encoder = "h264_v4l2m2m" if hwenc else "libx264"
        m3u8 = str(self.stream_dir / "stream.m3u8")

        cmd = [
            "ffmpeg", "-loglevel", "error",
            "-f", "v4l2",
            "-framerate", str(fps),      # tell v4l2 the input rate
            "-video_size", f"{width}x{height}",
            "-pixel_format", "bgr24",
            "-i", device,
            "-c:v", encoder,
        ]
        if not hwenc:
            cmd += ["-preset", "ultrafast", "-tune", "zerolatency"]
        cmd += [
            "-r", str(fps),              # force output rate
            "-b:v", f"{bitrate}k",
            "-f", "hls",
            "-hls_time", "1",
            "-hls_list_size", "4",
            "-hls_flags", "delete_segments+append_list",
            m3u8,
        ]
        log.info("Starting FFmpeg HLS: %s", " ".join(cmd))
        self.ffmpeg = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        self.ffmpeg.wait()
        log.warning("FFmpeg HLS process ended")

    def stop(self):
        if self.ffmpeg:
            self.ffmpeg.terminate()


# ── HTTP request handler ──────────────────────────────────────────────────────

class StreamHandler(http.server.BaseHTTPRequestHandler):

    # Injected by the server setup
    config: dict = {}
    mjpeg: MJPEGBroadcaster | None = None
    stream_dir: Path | None = None

    def log_message(self, fmt, *args):  # quieter logging
        if "stream.m3u8" not in (args[0] if args else ""):
            log.debug("HTTP %s %s", self.address_string(), fmt % args)

    def send_404(self):
        self.send_error(404, "Not Found")

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._serve_page()
        elif path == "/stream.mjpeg" and self.config.get("mode") == "mjpeg":
            self._serve_mjpeg()
        elif path.startswith("/stream/") and self.config.get("mode") == "hls":
            self._serve_hls_file(path[len("/stream/"):])
        else:
            self.send_404()

    def _serve_page(self):
        cfg = self.config
        html = PAGE_HTML \
            .replace("{{MODE}}",   cfg["mode"]) \
            .replace("{{DEVICE}}", cfg["device"]) \
            .replace("{{WIDTH}}",  str(cfg["width"])) \
            .replace("{{HEIGHT}}", str(cfg["height"]))
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_mjpeg(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=mjpegframe")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        q = self.mjpeg.add_client()
        try:
            while True:
                chunk = q.get(timeout=10)
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        finally:
            self.mjpeg.remove_client(q)

    def _serve_hls_file(self, filename: str):
        # Only allow safe filenames
        if ".." in filename or "/" in filename:
            self.send_404()
            return

        filepath = self.stream_dir / filename
        if not filepath.exists():
            self.send_response(503)
            self.send_header("Retry-After", "1")
            self.end_headers()
            return

        ctype = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/MP2T"
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


# ── Server setup & main ───────────────────────────────────────────────────────

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(description="HDMI Capture Stream Server")
    parser.add_argument("--device",  default="/dev/video0", help="v4l2 device")
    parser.add_argument("--width",   type=int, default=1920)
    parser.add_argument("--height",  type=int, default=1080)
    parser.add_argument("--port",    type=int, default=8080)
    parser.add_argument("--mode",    choices=["hls", "mjpeg"], default="hls")
    parser.add_argument("--bitrate", type=int, default=2000, help="HLS bitrate (kbps)")
    parser.add_argument("--hwenc",   action="store_true", help="Use h264_v4l2m2m (Pi 4/5)")
    parser.add_argument("--fps",     type=int, default=30, help="Capture framerate (default: 30)")
    args = parser.parse_args()

    stream_dir = Path("/tmp/hdmi-stream")
    config = {
        "mode":   args.mode,
        "device": args.device,
        "width":  args.width,
        "height": args.height,
    }

    # Build a handler class with shared state baked in
    mjpeg_broadcaster = MJPEGBroadcaster() if args.mode == "mjpeg" else None
    hls_streamer      = HLSStreamer(stream_dir) if args.mode == "hls" else None

    class Handler(StreamHandler):
        pass
    Handler.config     = config
    Handler.mjpeg      = mjpeg_broadcaster
    Handler.stream_dir = stream_dir

    # Start FFmpeg in a background thread
    if args.mode == "mjpeg":
        t = threading.Thread(
            target=mjpeg_broadcaster.run,
            args=(args.device, args.width, args.height, args.fps),
            daemon=True,
        )
        t.start()
    else:
        t = threading.Thread(
            target=hls_streamer.run,
            args=(args.device, args.width, args.height, args.bitrate, args.hwenc, args.fps),
            daemon=True,
        )
        t.start()

    # Start HTTP server
    server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    ip = get_local_ip()

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  HDMI Stream Server started")
    log.info("  Mode    : %s", args.mode.upper())
    log.info("  Device  : %s  (%dx%d @ %dfps)", args.device, args.width, args.height, args.fps)
    log.info("  Open    : http://%s:%d", ip, args.port)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    def shutdown(sig, frame):
        log.info("Shutting down…")
        server.shutdown()
        if mjpeg_broadcaster:
            mjpeg_broadcaster.stop()
        if hls_streamer:
            hls_streamer.stop()
        if stream_dir.exists():
            shutil.rmtree(stream_dir, ignore_errors=True)
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server.serve_forever()


if __name__ == "__main__":
    main()

