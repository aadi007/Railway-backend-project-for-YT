import re
import json
import logging
import requests
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


class YouTubeService:
    """
    Fetches YouTube video transcripts with real timestamps.
    Returns list of {text, start, duration} dicts.
    Three methods tried in order:
      1. youtube-transcript-api (fastest, works on most servers)
      2. YouTube timedtext API via page scraping (reliable fallback)
      3. yt-dlp (last resort)
    """

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?#]|$)',
            r'youtu\.be/([0-9A-Za-z_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def get_transcript_with_timestamps(
        video_id: str,
        language: str = 'en'
    ) -> Optional[List[Dict]]:
        """
        Returns list of: {'text': str, 'start': float, 'duration': float}
        """
        # ── Method 1: youtube-transcript-api ──────────────
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            ytt = YouTubeTranscriptApi()
            langs_to_try = list({language, 'en', 'en-US', 'en-GB', 'en-CA'})

            # Try each language
            for lang in langs_to_try:
                try:
                    fetched = ytt.fetch(video_id, languages=[lang])
                    data = [
                        {'text': t['text'], 'start': t['start'], 'duration': t.get('duration', 2.0)}
                        for t in fetched
                        if t.get('text', '').strip()
                    ]
                    if data:
                        logger.info(f"✅ Transcript via ytt-api ({lang}): {len(data)} segments")
                        return data
                except Exception:
                    continue

            # Try listing all available transcripts
            try:
                tlist = ytt.list(video_id)
                for transcript in tlist:
                    try:
                        fetched = transcript.fetch()
                        data = [
                            {'text': t['text'], 'start': t['start'], 'duration': t.get('duration', 2.0)}
                            for t in fetched
                            if t.get('text', '').strip()
                        ]
                        if data:
                            logger.info(f"✅ Transcript via ytt-api list: {len(data)} segments")
                            return data
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"ytt-api list failed: {e}")

        except ImportError:
            logger.warning("youtube-transcript-api not installed")
        except Exception as e:
            logger.warning(f"youtube-transcript-api error: {e}")

        # ── Method 2: YouTube page scraping ───────────────
        try:
            data = YouTubeService._fetch_via_page(video_id, language)
            if data:
                logger.info(f"✅ Transcript via page scraping: {len(data)} segments")
                return data
        except Exception as e:
            logger.warning(f"Page scraping failed: {e}")

        # ── Method 3: yt-dlp ──────────────────────────────
        try:
            data = YouTubeService._fetch_via_ytdlp(video_id, language)
            if data:
                logger.info(f"✅ Transcript via yt-dlp: {len(data)} segments")
                return data
        except Exception as e:
            logger.warning(f"yt-dlp failed: {e}")

        logger.error(f"❌ All transcript methods failed for {video_id}")
        return None

    @staticmethod
    def get_transcript(video_id: str, language: str = 'en') -> Optional[str]:
        """Plain text transcript (for backward compat)."""
        data = YouTubeService.get_transcript_with_timestamps(video_id, language)
        if not data:
            return None
        return ' '.join(seg['text'] for seg in data)

    @staticmethod
    def get_video_info(video_id: str) -> Dict:
        """Fetch video title and metadata."""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                # Extract title from page
                title_match = re.search(
                    r'"title"\s*:\s*"([^"]+)"', resp.text
                ) or re.search(
                    r'<title>([^<]+) - YouTube</title>', resp.text
                )
                title = title_match.group(1) if title_match else f'YouTube Video {video_id}'
                title = title.replace('\\u0026', '&').replace('\\/', '/').strip()
                return {
                    'video_id': video_id,
                    'url': url,
                    'title': title
                }
        except Exception as e:
            logger.warning(f"get_video_info failed: {e}")

        return {
            'video_id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'title': f'YouTube Video {video_id}'
        }

    # ── Private helpers ────────────────────────────────────

    @staticmethod
    def _fetch_via_page(video_id: str, language: str = 'en') -> Optional[List[Dict]]:
        """Scrape caption URL from YouTube video page."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        page = resp.text

        # Extract captionTracks from ytInitialPlayerResponse
        caption_url = None
        player_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;', page, re.DOTALL)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                tracks = (
                    player_data
                    .get('captions', {})
                    .get('playerCaptionsTracklistRenderer', {})
                    .get('captionTracks', [])
                )
                if tracks:
                    # Prefer requested language, then English, then any
                    chosen = None
                    for t in tracks:
                        lc = t.get('languageCode', '')
                        if lc.startswith(language):
                            chosen = t
                            break
                    if not chosen:
                        for t in tracks:
                            if t.get('languageCode', '').startswith('en'):
                                chosen = t
                                break
                    if not chosen:
                        chosen = tracks[0]
                    caption_url = chosen.get('baseUrl', '')
            except Exception:
                pass

        if not caption_url:
            # Simple regex fallback
            m = re.search(r'"baseUrl"\s*:\s*"(https://www\.youtube\.com/api/timedtext[^"]+)"', page)
            if m:
                caption_url = m.group(1).replace('\\u0026', '&').replace('\\/', '/')

        if not caption_url:
            return None

        # Request JSON3 format
        sep = '&' if '?' in caption_url else '?'
        caption_url += f"{sep}fmt=json3"

        cap_resp = requests.get(caption_url, headers=HEADERS, timeout=15)
        if cap_resp.status_code != 200:
            return None

        try:
            cap_data = cap_resp.json()
            events = cap_data.get('events', [])
            segments = []
            for event in events:
                start = event.get('tStartMs', 0) / 1000.0
                duration = event.get('dDurationMs', 2000) / 1000.0
                segs = event.get('segs', [])
                text = ' '.join(s.get('utf8', '') for s in segs).strip()
                text = text.replace('\n', ' ').strip()
                if text and text != ' ':
                    segments.append({'text': text, 'start': start, 'duration': duration})
            return segments if segments else None
        except Exception as e:
            logger.warning(f"Failed to parse caption JSON: {e}")
            return None

    @staticmethod
    def _fetch_via_ytdlp(video_id: str, language: str = 'en') -> Optional[List[Dict]]:
        """Fallback using yt-dlp."""
        try:
            import yt_dlp
        except ImportError:
            return None

        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            )
            all_subs = {**info.get('subtitles', {}), **info.get('automatic_captions', {})}
            if not all_subs:
                return None

            lang = language if language in all_subs else 'en' if 'en' in all_subs else list(all_subs.keys())[0]
            tracks = all_subs[lang]
            url = next((t['url'] for t in tracks if 'json3' in t.get('ext', '')), None)
            if not url:
                url = tracks[0].get('url', '')
            if not url:
                return None

            resp = requests.get(url, headers=HEADERS, timeout=15)
            try:
                cap_data = resp.json()
                events = cap_data.get('events', [])
                segments = []
                for event in events:
                    start = event.get('tStartMs', 0) / 1000.0
                    duration = event.get('dDurationMs', 2000) / 1000.0
                    segs = event.get('segs', [])
                    text = ' '.join(s.get('utf8', '') for s in segs).strip().replace('\n', ' ')
                    if text:
                        segments.append({'text': text, 'start': start, 'duration': duration})
                return segments if segments else None
            except Exception:
                return None
