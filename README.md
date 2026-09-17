# ah-dawn-al

Open-source downloader and preview tool for videos and images from selected social platforms.

## Features
- **Easy Interface:** Simple web-based interface built with Flask.
- **Focused:** Supports YouTube, TikTok, Twitter/X, and Snapchat links only.
- **Preview First:** Paste a link, import it, preview the media, then download.
- **High Quality:** Uses `ffmpeg` for merging high-quality video and audio streams.
- **Portable:** Designed to run anywhere with Docker.
- **Secure:** Includes configurations to keep your sensitive cookies and data private.

## How it works

### Python Logic
The application uses **Flask** as a lightweight web server to handle requests. When a URL is submitted:
1. It validates that the URL uses HTTP/HTTPS and points to a public address.
2. It accepts only YouTube, TikTok, Twitter/X, or Snapchat links.
3. It uses **yt-dlp** to verify that the link resolves to image or video media before opening or downloading it.

### Docker Architecture
- **Base Image:** Built on `python:3.11-slim` for a lightweight footprint.
- **FFmpeg:** Installed within the container to handle video merging and conversion.
- **Persistence:** Uses volumes to map local directories to the container, ensuring downloaded files persist on your host machine.

## Dependencies & Versions
- **Python:** 3.11
- **Flask:** Latest stable version
- **yt-dlp:** Latest nightly version available when the Docker image is built, with the EJS scripts and Deno for YouTube
- **FFmpeg:** Installed via system package manager

Downloads are sent to the user's browser. The server uses a temporary directory
for each download and removes it after the response closes. Rebuilding the Docker
image also refreshes yt-dlp; restarting an existing container does not.

## Setup Instructions

1. **Prerequisites:** Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed.
2. **Optional Cookies:** Create a `cookies.txt` file in this directory only if a site requires browser cookies.
3. **Download from GitHub and run:** In PowerShell, run:
   ```powershell
   git clone https://github.com/ah1al/ah-dawn-al.git
   cd ah-dawn-al
   .\run-docker.ps1
   ```

4. **Run from an existing local copy without Docker Desktop grouping:** In PowerShell, run:
   ```powershell
   .\run-docker.ps1
   ```

   This runs the container directly as `ah-dawn-al`, so Docker Desktop shows it as a single container instead of a Compose project with a nested service.

   Alternatively, if you prefer Docker Compose, run:
   ```bash
   docker-compose up -d
   ```
5. **Access:** Navigate to `http://localhost:5000` in your web browser.

### Optional cookie mount
If you need cookies, add this line under `volumes` in `docker-compose.yml`:

```yaml
      - "./cookies.txt:/app/cookies.txt:ro"
```

## Security
A `.gitignore` file is included to ensure `cookies.txt` and the `downloads/` directory are never pushed to GitHub. Please handle your `cookies.txt` responsibly.

The Docker Compose file publishes port `5000`, so devices on the same network can access the app through your computer's local IP address.

## License

This project is open source under the MIT License.

Copyright (c) 2026 ahmadalhoian

