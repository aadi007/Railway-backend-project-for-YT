import openai
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AIService:

    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_content(
        self,
        transcript: str,
        chunks: list,
        tone: str = "professional",
        language: str = "en",
        video_title: str = ""
    ) -> Optional[Dict]:

        try:
            # 🚀 ULTRA LOW COST INPUT
            chunk_summary = "\n".join(
                [f"{int(c['time'])}s: {c['text'][:200]}" for c in chunks[:10]]
            )

            prompt = f"""
You are a YouTube SEO expert.

Video Title: {video_title}

Use the following video segments:

{chunk_summary}

Generate:

1. Titles for each timestamp (short, 3-5 words)
2. SEO description (150 words)
3. 5 tags
4. 3 hashtags

Return ONLY JSON:
{{
 "timestamps": [{{"time": "0:00", "title": "Intro"}}],
 "description": "...",
 "tags": [],
 "hashtags": [],
 "title_suggestions": []
}}
"""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600,
            )

            raw = response.choices[0].message.content.strip()

            if raw.startswith("```"):
                raw = raw.replace("```json", "").replace("```", "")

            return json.loads(raw)

        except Exception as e:
            logger.error(f"AI error: {e}")
            return None
