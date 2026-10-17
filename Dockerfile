FROM python:3.12-slim

# ffmpeg edits the videos
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Clips, videos and the database live here: mount a persistent volume at /data
ENV REELBOT_STORAGE=/data
EXPOSE 8000
CMD ["python", "-m", "reelbot.app"]
