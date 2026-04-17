import openai
import os
import logging
import json
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_content(self, transcript: str, tone: str = "professional", language: str = "en") -> Optional[Dict]:
        try:
            prompt = f"""
Analyze this YouTube video transcript and generate:

1. **Timestamps**: Create 5-10 chapter timestamps with titles. Format: "0:00 Introduction", "2:30 Main Topic", etc.
   - Detect natural topic shifts
   - Keep titles concise (3-6 words)
   - Always start with "0:00 Introduction"

2. **SEO Description**: Write a compelling 150-300 word description
   - Include the primary topic in the first sentence
   - Tone: {tone}
   - Language: {language}
   - Make it engaging and SEO-optimized

3. **Tags**: Extract 5-10 relevant search keywords

4. **Hashtags**: Generate 3-5 relevant hashtags (with # symbol)

**Transcript:**
{transcript[:4000]}

**IMPORTANT**: Return ONLY a valid JSON object with this exact structure:
{{
  "timestamps": [{{"time": "0:00", "title": "Introduction"}}, {{"time": "2:30", "title": "Topic Name"}}],
  "description": "Your SEO description here...",
  "tags": ["tag1", "tag2", "tag3"],
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]
}}

Return ONLY the JSON object, no other text.
"""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Cheapest capable model ~$0.00015 per 1K tokens
                messages=[
                    {"role": "system", "content": "You are an expert YouTube SEO specialist. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown code blocks if present
            if raw.startswith('```json'):
                raw = raw[7:]
            if raw.startswith('```'):
                raw = raw[3:]
            if raw.endswith('```'):
                raw = raw[:-3]

            result = json.loads(raw.strip())
            logger.info("Successfully generated content from transcript")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return None
