import yt_dlp
import re
from typing import Optional, Dict
import logging
import json

logger = logging.getLogger(__name__)

class YouTubeService:

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    async def get_transcript(video_id: str, language: str = 'en') -> Optional[str]:
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': [language],
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})

                captions = None
                if language in subtitles:
                    captions = subtitles[language]
                elif language in automatic_captions:
                    captions = automatic_captions[language]

                if not captions:
                    return None

                subtitle_url = None
                caption_ext = None
                for caption in captions:
                    if caption['ext'] in ['json3', 'srv3', 'vtt']:
                        subtitle_url = caption['url']
                        caption_ext = caption['ext']
                        break

                if not subtitle_url:
                    return None

                import urllib.request
                response = urllib.request.urlopen(subtitle_url)
                subtitle_data = response.read().decode('utf-8')

                if caption_ext == 'json3' or 'json3' in subtitle_url:
                    data = json.loads(subtitle_data)
                    events = data.get('events', [])
                    text_segments = []
                    for event in events:
                        for seg in event.get('segs', []):
                            text = seg.get('utf8', '').strip()
                            if text:
                                text_segments.append(text)
                    return ' '.join(text_segments)
                else:
                    lines = subtitle_data.split('\n')
                    text_segments = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('WEBVTT') and '-->' not in line and not line.isdigit():
                            text_segments.append(line)
                    return ' '.join(text_segments)

        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return None

    @staticmethod
    async def get_video_info(video_id: str) -> Dict:
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = {'skip_download': True, 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return {
                    'video_id': video_id,
                    'video_url': video_url,
                    'title': info.get('title', f'YouTube Video {video_id}'),
                    'duration': info.get('duration', 0)
                }
        except Exception as e:
            logger.error(f"Error fetching video info for {video_id}: {e}")
            return {'video_id': video_id, 'video_url': f'https://www.youtube.com/watch?v={video_id}'}
