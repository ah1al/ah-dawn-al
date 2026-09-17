FROM python:3.11-slim
COPY --from=denoland/deno:bin-2.9.6 /deno /usr/local/bin/deno
ENV DENO_NO_UPDATE_CHECK=1 DENO_NO_PROMPT=1
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz
RUN deno --version && python -m yt_dlp --version
COPY ah-dawn-al.py .
EXPOSE 5000
CMD ["python", "ah-dawn-al.py"]
