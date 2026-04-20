import re
from typing import Optional, Dict, List
import logging
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
        try:
            # 🔥 Get ALL available transcripts (not just strict language)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            try:
                # ✅ Try exact language first
                transcript = transcript_list.find_transcript([language])
            except:
                try:
                    # ✅ Fallback to English variants
                    transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                except:
                    # ✅ FINAL fallback → auto-generated transcript
                    transcript = transcript_list.find_generated_transcript(['en'])

            transcript_data = transcript.fetch()

            # Combine text
            full_text = " ".join([item['text'] for item in transcript_data])

            logger.info(f"Transcript fetched successfully for {video_id}, length: {len(full_text)}")

            return full_text

        except TranscriptsDisabled:
            logger.error(f"Transcripts disabled for video {video_id}")
            return None

        except NoTranscriptFound:
            logger.error(f"No transcript found for video {video_id}")
            return None

        except Exception as e:
            logger.error(f"Transcript fetch error for {video_id}: {e}")
            return None

    @staticmethod
    def get_transcript_with_timestamps(video_id: str, language: str = 'en') -> Optional[List[Dict]]:
        """
        🔥 NEW: Returns transcript WITH timestamps (for accurate chapters)
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            try:
                transcript = transcript_list.find_transcript([language])
            except:
                try:
                    transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                except:
                    transcript = transcript_list.find_generated_transcript(['en'])

            return transcript.fetch()

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
