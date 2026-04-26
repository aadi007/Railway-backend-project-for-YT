from fastapi import FastAPI, APIRouter, HTTPException, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

from services.youtube_service import YouTubeService
from services.chunking_engine import ChunkingEngine
from services.ai_service import AIService
from services.supabase_service import SupabaseService

# Load env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Services
youtube_service = YouTubeService()
chunking_engine = ChunkingEngine()
ai_service = AIService(api_key=os.getenv('OPENAI_API_KEY'))
supabase_service = SupabaseService(
    url=os.getenv('SUPABASE_URL'),
    key=os.getenv('SUPABASE_ANON_KEY')
)

# App
app = FastAPI(title="YouTube SEO Generator API", version="2.1.0")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =======================
# MODELS
# =======================

class GenerateRequest(BaseModel):
    url: str
    tone: str = "professional"
    lang: str = "en"

class Timestamp(BaseModel):
    time: str
    title: str

class GenerateResponse(BaseModel):
    success: bool
    video_title: str = ""
    video_url: str = ""
    timestamps: List[Timestamp] = []
    description: str = ""
    tags: List[str] = []
    hashtags: List[str] = []
    title_suggestions: List[str] = []
    usage_remaining: Optional[int] = None
    error: Optional[str] = None

# =======================
# AUTH
# =======================

async def get_user_from_token(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "").strip()
        return await supabase_service.verify_user(token)
    except Exception as e:
        logger.error(f"Token error: {e}")
        return None

# =======================
# ROUTES
# =======================

@app.get("/")
async def home():
    return {"status": "API is live"}

@api_router.get("")
@api_router.get("/")
async def root():
    return {"message": "YouTube SEO API", "status": "running"}

# 🚀 MAIN API
@api_router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, authorization: Optional[str] = Header(None)):
    try:
        user = await get_user_from_token(authorization)

        # 1. Extract video ID
        video_id = YouTubeService.extract_video_id(request.url)
        if not video_id:
            return GenerateResponse(success=False, error="Invalid YouTube URL")

        logger.info(f"Processing video: {video_id}")

        # 2. Fetch transcript with timestamps
        transcript_data = await asyncio.to_thread(
            YouTubeService.get_transcript_with_timestamps,
            video_id,
            request.lang
        )

        if not transcript_data:
            return GenerateResponse(
                success=False,
                error="No captions available for this video"
            )

        # 3. Video info
        video_info = await asyncio.to_thread(
            YouTubeService.get_video_info,
            video_id
        )

        video_title = video_info.get('title', '')
        video_url = video_info.get('url', '')

        # 4. Chunking (FREE + IMPORTANT)
        chunks = chunking_engine.segment(transcript_data)

        # 🚀 ULTRA LOW COST INPUT
        compact_input = chunking_engine.to_chunk_summary(chunks)

        # 5. AI generation (LOW COST)
        generated = await ai_service.generate_content(
            transcript=compact_input,
            chunks=chunks,
            tone=request.tone,
            language=request.lang,
            video_title=video_title
        )

        if not generated:
            return GenerateResponse(success=False, error="AI generation failed")

        # 6. REAL timestamps (no AI guess)
        real_timestamps = chunking_engine.build_timestamps(chunks)

        timestamps = [
            Timestamp(time=t['time'], title="")
            for t in real_timestamps
        ]

        # Fill titles from AI
        ai_ts = generated.get("timestamps", [])
        for i in range(min(len(timestamps), len(ai_ts))):
            timestamps[i].title = ai_ts[i].get("title", "")

        # 7. Usage tracking
        usage_remaining = None
        if user:
            await supabase_service.log_generation(
                user_id=user['id'],
                video_url=video_url,
                video_title=video_title
            )
            await supabase_service.increment_usage(user['id'])

            profile = await supabase_service.get_or_create_profile(
                user['id'],
                user['email']
            )
            if profile:
                usage_remaining = profile.get('usage_count', 0)

        return GenerateResponse(
            success=True,
            video_title=video_title,
            video_url=video_url,
            timestamps=timestamps,
            description=generated.get("description", ""),
            tags=generated.get("tags", []),
            hashtags=generated.get("hashtags", []),
            title_suggestions=generated.get("title_suggestions", []),
            usage_remaining=usage_remaining
        )

    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        return GenerateResponse(
            success=False,
            error=str(e)
        )

# Register
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
