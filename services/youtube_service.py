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

    except Exception as e:
        logger.warning(f"⚠️ Primary transcript failed, switching to yt-dlp: {e}")

        # 🔥 FALLBACK METHOD (reliable)
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

                # pick first language available
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
