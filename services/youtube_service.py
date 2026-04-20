import re
import logging
from typing import Optional, Dict, List

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound
)

logger = logging.getLogger(__name__)


class YouTubeService:

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def get_transcript(video_id: str, language: str = 'en') -> Optional[str]:
        """
        ✅ Stable transcript fetch (NO yt-dlp, NO list_transcripts)
        Works reliably on Railway
        """
        try:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=[language, 'en', 'en-US', 'en-GB']
            )

            full_text = " ".join([item['text'] for item in transcript])

            logger.info(f"✅ Transcript fetched for {video_id}, length: {len(full_text)}")

            return full_text

        except TranscriptsDisabled:
            logger.error(f"❌ Transcripts disabled for video {video_id}")
            return None

        except NoTranscriptFound:
            logger.error(f"❌ No transcript found for video {video_id}")
            return None

        except Exception as e:
            logger.error(f"❌ Transcript fetch failed for {video_id}: {e}")
            return None

    @staticmethod
    def get_transcript_with_timestamps(video_id: str, language: str = 'en') -> Optional[List[Dict]]:
        """
        🔥 Returns transcript WITH timestamps (for future accurate chapters)
        """
        try:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=[language, 'en', 'en-US', 'en-GB']
            )

            return transcript  # includes start + duration

        except Exception as e:
            logger.error(f"Timestamp transcript error: {e}")
            return None

    @staticmethod
    async def get_video_info(video_id: str) -> Dict:
        return {
            'video_id': video_id,
            'video_url': f'https://www.youtube.com/watch?v={video_id}',
            'title': f'YouTube Video {video_id}',
            'duration': 0
        }
