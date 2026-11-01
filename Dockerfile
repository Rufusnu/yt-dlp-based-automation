FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg python3-mutagen \
    python3-brotli python3-certifi python3-requests python3-urllib3 ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip3 install --no-cache-dir --break-system-packages fastapi uvicorn itsdangerous
# yt-dlp is fetched at build time; the Settings page can update it later
ADD --chmod=755 https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp /usr/local/bin/yt-dlp
WORKDIR /srv
COPY app /srv/app
COPY static /srv/static
ENV LANG=C.UTF-8 PYTHONUTF8=1 PYTHONUNBUFFERED=1
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099"]
