import openai
import os
import logging
import json
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)

    # =========================
    # 🔹 Step 1: Split transcript
    # =========================
    def split_text(self, text: str, max_chars: int = 2000) -> List[str]:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    # =========================
    # 🔹 Step 2: Summarize chunk
    # =========================
    async def summarize_chunk(self, chunk: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this YouTube transcript chunk clearly:\n{chunk}"
                    }
                ],
                temperature=0.3,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Chunk summarization failed: {e}")
            return ""

    # =========================
    # 🔹 Step 3: Full summarization
    # =========================
    async def summarize_full_transcript(self, transcript: str) -> str:
        chunks = self.split_text(transcript, 2000)

        # 🔥 Limit chunks (cost control)
        chunks = chunks[:5]

        summaries = []
        for chunk in chunks:
            summary = await self.summarize_chunk(chunk)
            if summary:
                summaries.append(summary)

        combined = " ".join(summaries)

        logger.info(f"Transcript split into {len(chunks)} chunks")
        return combined

    # =========================
    # 🔹 Step 4: Final generation
    # =========================
    async def generate_content(self, transcript: str, tone: str = "professional", language: str = "en") -> Optional[Dict]:
        try:
            # 🔥 NEW: Summarize first
            summary = await self.summarize_full_transcript(transcript)

            prompt = f"""
Analyze this YouTube video summary and generate:

1. **Timestamps**: Create 5-10 chapter timestamps with titles.
   Format: "0:00 Introduction", "2:30 Topic Name"
   - Detect natural topic shifts
   - Keep titles concise (3-6 words)
   - Always start with "0:00 Introduction"

2. **SEO Description**: Write a compelling 150-300 word description
   - Include main topic early
   - Tone: {tone}
   - Language: {language}

3. **Tags**: 5-10 relevant keywords

4. **Hashtags**: 3-5 relevant hashtags

**Summary:**
{summary}

**IMPORTANT**: Return ONLY valid JSON:
{{
  "timestamps": [{{"time": "0:00", "title": "Introduction"}}],
  "description": "...",
  "tags": ["tag1"],
  "hashtags": ["#tag"]
}}
"""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert YouTube SEO specialist. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            raw = response.choices[0].message.content.strip()

            # Clean markdown if present
            if raw.startswith('```json'):
                raw = raw[7:]
            if raw.startswith('```'):
                raw = raw[3:]
            if raw.endswith('```'):
                raw = raw[:-3]

            result = json.loads(raw.strip())

            logger.info("Successfully generated content from summarized transcript")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return None
