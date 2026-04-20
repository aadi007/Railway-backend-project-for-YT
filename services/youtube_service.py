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
        try:
            # 🔥 PRIMARY METHOD (fast)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            try:
                transcript = transcript_list.find_transcript([language])
            except:
                try:
                    transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                except:
                    transcript = transcript_list.find_generated_transcript(['en'])

            transcript_data = transcript.fetch()

            full_text = " ".join([item['text'] for item in transcript_data])

            logger.info(f"✅ Transcript fetched via API for {video_id}, length: {len(full_text)}")

            return full_text

        except TranscriptsDisabled:
            logger.error(f"❌ Transcripts disabled for video {video_id}")
            return None

        except NoTranscriptFound:
            logger.error(f"❌ No transcript found for video {video_id}")
            return None

        except Exception as e:
            logger.warning(f"⚠️ Primary transcript failed, switching to yt-dlp: {e}")

            # 🔥 FALLBACK METHOD (reliable on Railway)
            try:
                import yt_dlp
                import requests
                import json

                ydl_opts = {
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'quiet': True,
                    'no_warnings': True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}",
                        download=False
                    )

                    subtitles = info.get('automatic_captions') or info.get('subtitles')

                    if not subtitles:
                        logger.error(f"❌ No subtitles found even via yt-dlp for {video_id}")
                        return None

                    # pick first available language
                    lang = list(subtitles.keys())[0]
                    subtitle_url = subtitles[lang][0]['url']

                    res = requests.get(subtitle_url)
                    data = res.text

                    # 🔥 Handle JSON subtitles properly
                    if "json3" in subtitle_url:
                        parsed = json.loads(data)
                        events = parsed.get("events", [])

                        text = []
                        for event in events:
                            for seg in event.get("segs", []):
                                if "utf8" in seg:
                                    text.append(seg["utf8"])

                        final_text = " ".join(text)

                        logger.info(f"✅ Transcript fetched via yt-dlp fallback, length: {len(final_text)}")

                        return final_text

                    # fallback raw
                    return data[:5000]

            except Exception as e:
                logger.error(f"❌ Fallback transcript failed for {video_id}: {e}")
                return None

    @staticmethod
    def get_transcript_with_timestamps(video_id: str, language: str = 'en') -> Optional[List[Dict]]:
        """
        🔥 Returns transcript WITH timestamps (for future accurate chapters)
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
