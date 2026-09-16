FROM python:3.11-slim

# تثبيت ffmpeg لدمج جودات الفيديو العالية
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت Flask لتحويل البرنامج لموقع ويب و yt-dlp لتحميل الوسائط
RUN pip install --no-cache-dir flask yt-dlp

# نسخ الملفات المطلوبة
COPY ah-dawn-al.py .

# إنشاء مجلد التحميلات
RUN mkdir /app/downloads

# فتح المنفذ 5000
EXPOSE 5000

CMD ["python", "ah-dawn-al.py"]
