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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ── Services ──────────────────────────────────────────────
youtube_service = YouTubeService()
chunking_engine = ChunkingEngine()
ai_service      = AIService(api_key=os.getenv('OPENAI_API_KEY'))
supabase_service = SupabaseService(
    url=os.getenv('SUPABASE_URL'),
    key=os.getenv('SUPABASE_ANON_KEY')
)

# ── App ───────────────────────────────────────────────────
app = FastAPI(title="YouTube SEO Generator API", version="2.0.0")
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ── Models ────────────────────────────────────────────────
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

class HistoryItem(BaseModel):
    video_url: str
    video_title: str
    created_at: str

class HistoryResponse(BaseModel):
    success: bool
    history: List[HistoryItem] = []


# ── Auth helper ───────────────────────────────────────────
async def get_user_from_token(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "").strip()
        return await supabase_service.verify_user(token)
    except Exception as e:
        logger.error(f"Token error: {e}")
        return None


# ── Routes ────────────────────────────────────────────────
@app.get("/")
async def home():
    return {"message": "YouTube SEO Generator API", "status": "running", "version": "2.0.0"}

@api_router.get("")
@api_router.get("/")
async def root():
    return {"message": "YouTube SEO Generator API", "status": "running", "version": "2.0.0"}


@api_router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    authorization: Optional[str] = Header(None)
):
    try:
        # 1. Auth (optional — works without login for free tier)
        user = await get_user_from_token(authorization)
        logger.info(f"Request from {'user:' + user['email'] if user else 'anonymous'}")

        # 2. Extract video ID
        video_id = YouTubeService.extract_video_id(request.url)
        if not video_id:
            return GenerateResponse(success=False, error="Invalid YouTube URL. Please paste a valid YouTube video link.")

        logger.info(f"Processing video: {video_id}")

        # 3. Fetch transcript WITH real timestamps (runs in thread to avoid blocking)
        transcript_data = await asyncio.to_thread(
            YouTubeService.get_transcript_with_timestamps,
            video_id,
            request.lang
        )

        if not transcript_data:
            return GenerateResponse(
                success=False,
                error="No captions available for this video. Please try a video with subtitles/captions enabled."
            )

        logger.info(f"Transcript segments: {len(transcript_data)}")

        # 4. Get video title
        video_info = await asyncio.to_thread(YouTubeService.get_video_info, video_id)
        video_title = video_info.get('title', f'YouTube Video {video_id}')
        video_url   = video_info.get('url', f'https://www.youtube.com/watch?v={video_id}')

        # 5. Chunking engine — segment transcript into logical chapters
        chunks = chunking_engine.segment(transcript_data)
        logger.info(f"Chunks created: {len(chunks)}")

        # 6. Build plain text for AI (use chunked summary)
        plain_transcript = ChunkingEngine.to_plain_text(transcript_data)

        # 7. AI generation
        generated = await ai_service.generate_content(
            transcript=plain_transcript,
            chunks=chunks,
            tone=request.tone,
            language=request.lang,
            video_title=video_title
        )

        if not generated:
            return GenerateResponse(success=False, error="Failed to generate content. Please try again.")

        # 8. Build timestamps — prefer real ones from chunking engine
        real_timestamps = chunking_engine.build_timestamps(chunks)
        ai_timestamps   = generated.get('timestamps', [])

        # Use real timestamps if we got enough, otherwise use AI ones
        if len(real_timestamps) >= 3:
            timestamps = [Timestamp(time=t['time'], title=t['title']) for t in real_timestamps]
        else:
            timestamps = [Timestamp(time=t['time'], title=t['title']) for t in ai_timestamps]

        # 9. Log usage if authenticated
        usage_remaining = None
        if user:
            await supabase_service.log_generation(
                user_id=user['id'],
                video_url=video_url,
                video_title=video_title
            )
            await supabase_service.increment_usage(user['id'])
            profile = await supabase_service.get_or_create_profile(user['id'], user['email'])
            if profile:
                usage_remaining = profile.get('usage_count', 0)

        logger.info(f"Successfully generated content for {video_id}")

        return GenerateResponse(
            success=True,
            video_title=video_title,
            video_url=video_url,
            timestamps=timestamps,
            description=generated.get('description', ''),
            tags=generated.get('tags', []),
            hashtags=generated.get('hashtags', []),
            title_suggestions=generated.get('title_suggestions', []),
            usage_remaining=usage_remaining
        )

    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        return GenerateResponse(success=False, error=f"An error occurred: {str(e)}")


@api_router.get("/history", response_model=HistoryResponse)
async def get_history(authorization: Optional[str] = Header(None)):
    try:
        user = await get_user_from_token(authorization)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        history_data = await supabase_service.get_user_history(user['id'])
        items = [
            HistoryItem(
                video_url=item['video_url'],
                video_title=item['video_title'],
                created_at=item['created_at']
            ) for item in history_data
        ]
        return HistoryResponse(success=True, history=items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"History error: {e}")
        return HistoryResponse(success=False, history=[])


@api_router.get("/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    try:
        user = await get_user_from_token(authorization)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        profile = await supabase_service.get_or_create_profile(user['id'], user['email'])
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {
            "success": True,
            "profile": {
                "email": profile['email'],
                "plan": profile.get('plan', 'free'),
                "usage_count": profile.get('usage_count', 0)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Register ──────────────────────────────────────────────
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
