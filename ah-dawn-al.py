from flask import Flask, Response, render_template_string, request, jsonify, send_file
import yt_dlp
import os
import ipaddress
import socket
import urllib.request
import tempfile
import shutil
from urllib.parse import quote, unquote, urlparse

# ah-dawn-al
# Copyright (c) 2026 ahmadalhoian
# Released under the MIT License.

app = Flask(__name__)

# ================= الإعدادات الثابتة =================
COOKIES_PATH = r"/app/cookies.txt"
DOWNLOAD_PATH = r"/app/downloads"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
ALLOWED_DOMAINS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "snapchat.com",
    "www.snapchat.com",
    "story.snapchat.com",
)

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "الرابط يجب أن يبدأ بـ http أو https"

    host = parsed.hostname
    if not host:
        return False, "الرابط غير صالح"

    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, "تعذر الوصول إلى عنوان الموقع"

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, "لا يمكن استخدام روابط داخلية أو محلية"

    return True, ""

def is_allowed_platform_url(url):
    host = urlparse(url).hostname or ""
    host = host.lower()
    return host in ALLOWED_DOMAINS or any(host.endswith(f".{domain}") for domain in ALLOWED_DOMAINS)

def is_image_or_video_info(info):
    if not info:
        return False
    if info.get('_type') == 'playlist':
        entries = [entry for entry in info.get('entries', []) if entry]
        return bool(entries) and all(is_image_or_video_info(entry) for entry in entries)
    if info.get('vcodec') and info.get('vcodec') != 'none':
        return True
    if info.get('ext') in {'jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'mov', 'webm', 'mkv'}:
        return True
    formats = info.get('formats') or []
    return any(fmt.get('vcodec') and fmt.get('vcodec') != 'none' for fmt in formats)

def platform_name(url):
    host = (urlparse(url).hostname or "").lower()
    if "tiktok" in host:
        return "tiktok"
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "twitter" in host or host.endswith("x.com"):
        return "twitter"
    if "snapchat" in host:
        return "snapchat"
    return "media"

def media_type_from_info(info):
    ext = (info.get('ext') or "").lower()
    if ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "image"
    return "video"

def youtube_embed_url(url):
    parsed = urlparse(url)
    video_id = None
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        if parsed.path == "/watch":
            from urllib.parse import parse_qs
            video_id = parse_qs(parsed.query).get('v', [None])[0]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/")[2]
        elif parsed.path.startswith("/v/"):
            video_id = parsed.path.split("/")[2]
    elif parsed.hostname == "youtu.be":
        video_id = parsed.path.lstrip("/")

    if not video_id:
        return None
    return f'https://www.youtube.com/embed/{video_id}'

def tiktok_embed_url(info, url):
    video_id = info.get('id')
    if not video_id:
        path_parts = [part for part in urlparse(url).path.split('/') if part]
        if 'video' in path_parts:
            index = path_parts.index('video')
            if index + 1 < len(path_parts):
                video_id = path_parts[index + 1]
    if not video_id:
        return None
    return f'https://www.tiktok.com/embed/v2/{video_id}'

def preview_media_url(info):
    if info.get('url') and media_type_from_info(info) == "image":
        return info.get('url')
    formats = info.get('formats') or []
    playable_formats = [
        fmt for fmt in formats
        if fmt.get('url')
        and fmt.get('vcodec')
        and fmt.get('vcodec') != 'none'
        and (fmt.get('ext') in {'mp4', 'webm'} or 'mp4' in (fmt.get('format_note') or '').lower())
    ]
    if playable_formats:
        with_audio = [fmt for fmt in playable_formats if fmt.get('acodec') and fmt.get('acodec') != 'none']
        candidates = with_audio or playable_formats
        return candidates[-1].get('url')
    return info.get('url')

def twitter_preview_url(info):
    formats = info.get('formats') or []
    playable_formats = [
        fmt for fmt in formats
        if fmt.get('url')
        and (fmt.get('ext') in {'mp4', 'webm'} or '.mp4' in (fmt.get('url') or '').lower())
        and fmt.get('height')
    ]
    if playable_formats:
        candidates = [fmt for fmt in playable_formats if (fmt.get('height') or 0) <= 720] or playable_formats
        candidates.sort(key=lambda fmt: (fmt.get('height') or 0, fmt.get('tbr') or 0))
        return candidates[-1].get('url')
    return preview_media_url(info)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Pro Downloader</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1a1a1a; color: white; min-height: 100vh; margin: 0; padding: 18px; display: flex; justify-content: center; align-items: center; }
        .container { background-color: #2d2d2d; padding: 22px; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; width: min(620px, 100%); }
        h1 { color: #3498db; margin: 0 0 18px; font-size: 24px; }
        .version-tag { font-size: 12px; color: #888; text-align: right; margin-bottom: 5px; font-weight: normal; }
        .input-row { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; align-items: center; direction: ltr; margin-bottom: 8px; }
        input { min-width: 0; width: 100%; padding: 12px; border-radius: 8px; border: none; font-size: 14px; text-align: right; direction: ltr; }
        button { padding: 12px 16px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; transition: 0.3s; white-space: nowrap; }
        .btn-clear { background-color: #e74c3c; color: white; }
        .btn-clear:hover { background-color: #c0392b; }
        .btn-paste { background-color: #f39c12; color: white; }
        .btn-paste:hover { background-color: #e67e22; }
        .btn-import { background-color: #3498db; color: white; width: 100%; margin-top: 8px; }
        .btn-import:hover { background-color: #2980b9; }
        .btn-download { background-color: #2ecc71; color: white; width: 100%; margin-top: 14px; display: none; }
        .btn-download:hover { background-color: #27ae60; }
        #status { margin-top: 16px; font-size: 14px; color: #bbb; min-height: 22px; }
        .preview { display: none; margin-top: 16px; border-radius: 12px; overflow: hidden; background: #111; }
        .preview video, .preview img, .preview iframe { width: 100%; display: block; background: #000; border: 0; }
        .preview video, .preview img { max-height: 420px; object-fit: contain; }
        .preview iframe { height: 620px; }
        .preview-title { text-align: right; padding: 10px 12px; color: #ddd; font-size: 14px; background: #242424; overflow-wrap: anywhere; }
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 2s linear infinite; display: none; margin: 14px auto 0; }
        @media (max-width: 520px) {
            .container { padding: 16px; }
            h1 { font-size: 20px; }
            input::placeholder { font-size: 12px; }
            .input-row { grid-template-columns: 1fr auto auto; }
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="version-tag">v1.0.2</div>
        <h1>🚀 Universal Pro Downloader</h1>
        <div class="input-row">
            <input type="text" id="url" placeholder="رابط فيديو...">
            <button class="btn-paste" onclick="pasteUrl()">لصق</button>
            <button class="btn-clear" onclick="clearUrl()">تنظيف</button>
        </div>
        <button class="btn-import" onclick="importMedia()">بحث</button>
        <div id="loader" class="loader"></div>
        <div id="status">جاهز للاستخدام</div>
        <button id="downloadBtn" class="btn-download" onclick="downloadMedia()">تحميل</button>
        <div id="preview" class="preview">
            <div id="previewTitle" class="preview-title"></div>
            <div id="previewMedia"></div>
        </div>
    </div>

    <script>
        let importedUrl = "";

        async function pasteUrl() {
            try {
                const text = await navigator.clipboard.readText();
                document.getElementById('url').value = text;
            } catch (err) {
                alert("تعذر الوصول إلى الحافظة");
            }
        }

        function clearUrl() {
            document.getElementById('url').value = "";
            document.getElementById('preview').style.display = "none";
            document.getElementById('previewMedia').innerHTML = "";
            document.getElementById('downloadBtn').style.display = "none";
            document.getElementById('status').innerText = "تم التنظيف";
        }

        function setLoading(isLoading, message) {
            const status = document.getElementById('status');
            const loader = document.getElementById('loader');
            status.innerText = message;
            status.style.color = "#bbb";
            loader.style.display = isLoading ? "block" : "none";
        }

        async function importMedia() {
            const url = document.getElementById('url').value.trim();
            const preview = document.getElementById('preview');
            const previewMedia = document.getElementById('previewMedia');
            const previewTitle = document.getElementById('previewTitle');
            const downloadBtn = document.getElementById('downloadBtn');
            if (!url) { setStatus("❌ يرجى إدخال الرابط أولاً!", "red"); return; }

            // إذا كان الرابط يوتيوب، قم بالتحميل مباشرة
            if (url.includes('youtube.com') || url.includes('youtu.be')) {
                importedUrl = url;
                downloadMedia();
                return;
            }

            importedUrl = "";
            preview.style.display = "none";
            previewMedia.innerHTML = "";
            downloadBtn.style.display = "none";
            setLoading(true, "⏳ جاري الاستيراد...");

            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url, action: 'preview'})
                });
                const result = await response.json();
                if (result.success) {
                    importedUrl = url;
                    previewTitle.innerText = result.title || "تم استيراد الوسائط";
                    previewMedia.innerHTML = "";
                    if (result.media_type === "embed") {
                        const frame = document.createElement("iframe");
                        frame.src = result.url;
                        frame.allow = "autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share";
                        frame.allowFullscreen = true;
                        previewMedia.appendChild(frame);
                    } else if (result.media_type === "image") {
                        const image = document.createElement("img");
                        image.src = result.url;
                        image.alt = "preview";
                        previewMedia.appendChild(image);
                    } else {
                        const video = document.createElement("video");
                        video.src = result.url;
                        video.controls = true;
                        video.playsInline = true;
                        previewMedia.appendChild(video);
                    }
                    preview.style.display = "block";
                    downloadBtn.style.display = "block";
                    setStatus(result.message, "#2ecc71");
                } else {
                    setStatus("❌ " + result.message, "red");
                }
            } catch (e) {
                setStatus("❌ حدث خطأ في الاتصال بالسيرفر", "red");
            } finally {
                document.getElementById('loader').style.display = "none";
            }
        }

        async function downloadMedia() {
            if (!importedUrl) { setStatus("❌ استورد الرابط أولاً", "red"); return; }
            setLoading(true, "⏳ جاري التحميل...");
            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: importedUrl, action: 'download'})
                });
                const contentType = response.headers.get('content-type') || '';
                if (!response.ok || contentType.includes('application/json')) {
                    const result = await response.json();
                    setStatus("❌ " + (result.message || "تعذر تنزيل الملف"), "red");
                    return;
                }
                const blob = await response.blob();
                const objectUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = objectUrl;
                link.download = '';
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(objectUrl);
                setStatus("✅ تم إرسال الملف إلى جهازك", "#2ecc71");
            } catch (e) {
                setStatus("❌ حدث خطأ في الاتصال بالسيرفر", "red");
            } finally {
                document.getElementById('loader').style.display = "none";
            }
        }

        function setStatus(message, color) {
            const status = document.getElementById('status');
            status.innerText = message;
            status.style.color = color;
        }
    </script>
</body>
</html>
"""

def get_yt_options(download=True):
    options = {
        'user_agent': "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
        'retries': 10,
        'extractor_retries': 10,
        'fragment_retries': 10,
        'socket_timeout': 30,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'add_header': [
            'Referer:https://www.youtube.com/',
            'Accept-Language:en-US,en;q=0.9'
        ]
    }
    if os.path.exists(COOKIES_PATH) and os.path.getsize(COOKIES_PATH) > 0:
        options['cookiefile'] = COOKIES_PATH
    if download:
        options.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(DOWNLOAD_PATH, '%(extractor_key)s_%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        })
    return options

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/execute', methods=['POST'])
def execute():
    data = request.json
    url = data.get('url')
    action = data.get('action')

    try:
        is_valid, error_message = validate_public_url(url)
        if not is_valid:
            return jsonify({'success': False, 'message': error_message})

        if not is_allowed_platform_url(url):
            return jsonify({'success': False, 'message': 'المسموح فقط روابط YouTube أو TikTok أو Twitter/X أو Snapchat'})

        if action == 'download':
            with yt_dlp.YoutubeDL(get_yt_options(download=False)) as ydl:
                info = ydl.extract_info(url, download=False)
            if not is_image_or_video_info(info):
                return jsonify({'success': False, 'message': 'الرابط لا يحتوي على صورة أو فيديو قابل للتحميل'})
            temp_dir = tempfile.mkdtemp(prefix='ah-dawn-al-', dir=os.environ.get('APP_TEMP_DIR'))
            try:
                download_options = get_yt_options(download=True)
                download_options['outtmpl'] = os.path.join(temp_dir, f'{platform_name(url)}_%(id)s.%(ext)s')
                with yt_dlp.YoutubeDL(download_options) as ydl:
                    ydl.download([url])
                files = [os.path.join(temp_dir, name) for name in os.listdir(temp_dir)
                         if os.path.isfile(os.path.join(temp_dir, name))]
                if not files:
                    return jsonify({'success': False, 'message': 'لم يتم إنشاء ملف قابل للتنزيل'})
                output_path = max(files, key=os.path.getmtime)
                response = send_file(output_path, as_attachment=True,
                                     download_name=os.path.basename(output_path))
                response.direct_passthrough = False
                response.call_on_close(lambda path=temp_dir: shutil.rmtree(path, ignore_errors=True))
                temp_dir = None
                return response
            finally:
                if temp_dir is not None:
                    shutil.rmtree(temp_dir, ignore_errors=True)

        elif action == 'preview':
            with yt_dlp.YoutubeDL(get_yt_options(download=False)) as ydl:
                info = ydl.extract_info(url, download=False)
            if not is_image_or_video_info(info):
                return jsonify({'success': False, 'message': 'الرابط لا يحتوي على صورة أو فيديو قابل للفتح'})
            if platform_name(url) == 'tiktok':
                embed_url = tiktok_embed_url(info, url)
                if not embed_url:
                    return jsonify({'success': False, 'message': 'لم يتم العثور على رابط عرض TikTok'})
                return jsonify({
                    'success': True,
                    'message': '✨ تم استيراد الوسائط',
                    'url': embed_url,
                    'title': info.get('title') or 'وسائط مستوردة',
                    'media_type': 'embed',
                })
            if platform_name(url) == 'youtube':
                embed_url = youtube_embed_url(url)
                if not embed_url:
                    return jsonify({'success': False, 'message': 'لم يتم العثور على رابط عرض YouTube'})
                return jsonify({
                    'success': True,
                    'message': '✨ تم استيراد الوسائط',
                    'url': embed_url,
                    'title': info.get('title') or 'وسائط مستوردة',
                    'media_type': 'embed',
                })
            if platform_name(url) == 'twitter':
                video_url = twitter_preview_url(info)
                if not video_url:
                    return jsonify({'success': False, 'message': 'لم يتم العثور على رابط عرض X'})
                return jsonify({
                    'success': True,
                    'message': '✨ تم استيراد الوسائط',
                    'url': f'/stream?source={quote(url, safe="")}',
                    'title': info.get('title') or 'وسائط مستوردة',
                    'media_type': media_type_from_info(info),
                })
            video_url = preview_media_url(info)
            if video_url:
                return jsonify({
                    'success': True,
                    'message': '✨ تم استيراد الوسائط',
                    'url': f'/stream?source={quote(url, safe="")}',
                    'title': info.get('title') or 'وسائط مستوردة',
                    'media_type': media_type_from_info(info),
                })
            return jsonify({'success': False, 'message': 'لم يتم العثور على رابط معاينة مباشر'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/stream')
def stream_media():
    source = unquote(request.args.get('source', ''))
    is_valid, error_message = validate_public_url(source)
    if not is_valid:
        return error_message, 400
    if not is_allowed_platform_url(source):
        return 'الرابط غير مسموح', 400

    with yt_dlp.YoutubeDL(get_yt_options(download=False)) as ydl:
        info = ydl.extract_info(source, download=False)
    if not is_image_or_video_info(info):
        return 'الرابط لا يحتوي على وسائط قابلة للعرض', 400

    if platform_name(source) == 'twitter':
        media_url = twitter_preview_url(info)
    else:
        media_url = preview_media_url(info)
    if not media_url:
        return 'لم يتم العثور على رابط معاينة مباشر', 404

    headers = {'User-Agent': USER_AGENT}
    headers.update(info.get('http_headers') or {})
    range_header = request.headers.get('Range')
    if range_header:
        headers['Range'] = range_header

    upstream_request = urllib.request.Request(media_url, headers=headers)
    upstream = urllib.request.urlopen(upstream_request, timeout=30)
    response_headers = {
        'Content-Type': upstream.headers.get('Content-Type', 'video/mp4'),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-store',
    }
    for header in ('Content-Length', 'Content-Range'):
        value = upstream.headers.get(header)
        if value:
            response_headers[header] = value

    status = 206 if upstream.headers.get('Content-Range') else 200
    def generate():
        try:
            while True:
                chunk = upstream.read(1024 * 256)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    return Response(generate(), status=status, headers=response_headers)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
