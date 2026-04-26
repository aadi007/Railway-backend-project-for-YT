import re
import json
import logging
import requests
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}


class YouTubeService:

    # -------------------------------
    # Extract Video ID
    # -------------------------------
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r"(?:v=|/)([0-9A-Za-z_-]{11})",
            r"youtu\.be/([0-9A-Za-z_-]{11})",
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    # -------------------------------
    # MAIN FUNCTION (IMPORTANT)
    # -------------------------------
    @staticmethod
    def get_transcript_with_timestamps(
        video_id: str,
        language: str = "en",
    ) -> Optional[List[Dict]]:

        logger.info(f"Fetching transcript for {video_id}")

        # 1️⃣ TRY youtube-transcript-api (BEST)
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            # Try preferred languages
            langs = [language, "en", "hi", "en-US", "en-GB"]

            for lang in langs:
                try:
                    data = YouTubeTranscriptApi.get_transcript(
                        video_id,
                        languages=[lang]
                    )

                    result = [
                        {
                            "text": x["text"],
                            "start": x["start"],
                            "duration": x.get("duration", 2.0),
                        }
                        for x in data
                        if x.get("text", "").strip()
                    ]

                    if result:
                        logger.info(f"✅ Transcript found via API ({lang})")
                        return result

                except Exception as e:
                    logger.warning(f"Lang {lang} failed: {e}")

            # Try auto captions
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

                for transcript in transcript_list:
                    try:
                        data = transcript.fetch()

                        result = [
                            {
                                "text": x["text"],
                                "start": x["start"],
                                "duration": x.get("duration", 2.0),
                            }
                            for x in data
                            if x.get("text", "").strip()
                        ]

                        if result:
                            logger.info("✅ Auto transcript used")
                            return result

                    except Exception:
                        continue

            except Exception as e:
                logger.warning(f"Transcript list failed: {e}")

        except Exception as e:
            logger.warning(f"youtube-transcript-api failed: {e}")

        # 2️⃣ FALLBACK: SCRAPE YOUTUBE PAGE
        try:
            data = YouTubeService._fetch_via_page(video_id, language)
            if data:
                logger.info("✅ Transcript via page scraping")
                return data
        except Exception as e:
            logger.warning(f"Page scraping failed: {e}")

        # 3️⃣ LAST FALLBACK: yt-dlp
        try:
            data = YouTubeService._fetch_via_ytdlp(video_id)
            if data:
                logger.info("✅ Transcript via yt-dlp")
                return data
        except Exception as e:
            logger.warning(f"yt-dlp failed: {e}")

        logger.error("❌ ALL transcript methods failed")
        return None

    # -------------------------------
    # SIMPLE TEXT VERSION
    # -------------------------------
    @staticmethod
    def get_transcript(video_id: str, language: str = "en") -> Optional[str]:
        data = YouTubeService.get_transcript_with_timestamps(video_id, language)
        if not data:
            return None
        return " ".join(x["text"] for x in data)

    # -------------------------------
    # VIDEO INFO
    # -------------------------------
    @staticmethod
    def get_video_info(video_id: str) -> Dict:
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            resp = requests.get(url, headers=HEADERS, timeout=10)

            if resp.status_code == 200:
                title_match = re.search(
                    r"<title>(.*?)</title>", resp.text
                )
                title = (
                    title_match.group(1).replace(" - YouTube", "")
                    if title_match
                    else f"Video {video_id}"
                )

                return {
                    "video_id": video_id,
                    "url": url,
                    "title": title.strip(),
                }

        except Exception as e:
            logger.warning(f"Video info error: {e}")

        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": f"Video {video_id}",
        }

    # -------------------------------
    # PAGE SCRAPING
    # -------------------------------
    @staticmethod
    def _fetch_via_page(video_id: str, language: str) -> Optional[List[Dict]]:
        url = f"https://www.youtube.com/watch?v={video_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)

        if resp.status_code != 200:
            return None

        match = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?});", resp.text)

        if not match:
            return None

        data = json.loads(match.group(1))

        tracks = (
            data.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )

        if not tracks:
            return None

        caption_url = tracks[0]["baseUrl"]

        resp = requests.get(caption_url + "&fmt=json3", headers=HEADERS, timeout=10)
        cap = resp.json()

        segments = []
        for event in cap.get("events", []):
            text = " ".join(
                s.get("utf8", "") for s in event.get("segs", [])
            ).strip()

            if text:
                segments.append({
                    "text": text,
                    "start": event.get("tStartMs", 0) / 1000,
                    "duration": event.get("dDurationMs", 2000) / 1000,
                })

        return segments or None

    # -------------------------------
    # YT-DLP FALLBACK
    # -------------------------------
    @staticmethod
    def _fetch_via_ytdlp(video_id: str) -> Optional[List[Dict]]:
        try:
            import yt_dlp
        except ImportError:
            return None

        ydl_opts = {"quiet": True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False,
            )

            subs = info.get("subtitles") or info.get("automatic_captions")
            if not subs:
                return None

            lang = list(subs.keys())[0]
            url = subs[lang][0]["url"]

            resp = requests.get(url, headers=HEADERS, timeout=10)
            data = resp.json()

            segments = []
            for event in data.get("events", []):
                text = " ".join(
                    s.get("utf8", "") for s in event.get("segs", [])
                ).strip()

                if text:
                    segments.append({
                        "text": text,
                        "start": event.get("tStartMs", 0) / 1000,
                        "duration": event.get("dDurationMs", 2000) / 1000,
                    })

            return segments or None
