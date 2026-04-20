import re
from typing import Optional, Dict
import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled

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
            # Fetch transcript using youtube-transcript-api
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])

            # Combine all text
            full_text = " ".join([item['text'] for item in transcript])

            return full_text

        except TranscriptsDisabled:
            logger.error(f"Transcripts disabled for video {video_id}")
            return None

        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return None

    @staticmethod
    async def get_video_info(video_id: str) -> Dict:
        try:
            # Since yt-dlp is removed, keep minimal info
            return {
                'video_id': video_id,
                'video_url': f'https://www.youtube.com/watch?v={video_id}',
                'title': f'YouTube Video {video_id}',
                'duration': 0
            }

        except Exception as e:
            logger.error(f"Error fetching video info for {video_id}: {e}")
            return {
                'video_id': video_id,
                'video_url': f'https://www.youtube.com/watch?v={video_id}'
            }
