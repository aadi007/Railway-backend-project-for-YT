from fastapi import FastAPI, APIRouter, HTTPException, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# Import services
from services.youtube_service import YouTubeService
from services.ai_service import AIService
from services.supabase_service import SupabaseService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize services
youtube_service = YouTubeService()
ai_service = AIService(api_key=os.getenv('OPENAI_API_KEY'))
supabase_service = SupabaseService(
    url=os.getenv('SUPABASE_URL'),
    key=os.getenv('SUPABASE_ANON_KEY')
)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

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
    usage_remaining: Optional[int] = None
    error: Optional[str] = None

class HistoryItem(BaseModel):
    video_url: str
    video_title: str
    created_at: str

class HistoryResponse(BaseModel):
    success: bool
    history: List[HistoryItem] = []


# ==================== HELPERS ====================

async def get_user_from_token(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "")
        return await supabase_service.verify_user(token)
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


# ==================== ENDPOINTS ====================

@api_router.get("/")
async def root():
    return {"message": "YouTube Timestamp & SEO API", "status": "running"}


@api_router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, authorization: Optional[str] = Header(None)):
    try:
        user = await get_user_from_token(authorization)

        video_id = youtube_service.extract_video_id(request.url)
        if not video_id:
            return GenerateResponse(success=False, error="Invalid YouTube URL")

        logger.info(f"Processing video: {video_id}")
        video_info = await youtube_service.get_video_info(video_id)
        video_url = video_info['video_url']
        video_title = video_info.get('title', f'YouTube Video {video_id}')

        transcript = await youtube_service.get_transcript(video_id, request.lang)
        if not transcript:
            return GenerateResponse(success=False, error="No transcript available for this video. Video might not have captions.")

        logger.info(f"Transcript fetched: {len(transcript)} characters")

        generated_content = await ai_service.generate_content(transcript=transcript, tone=request.tone, language=request.lang)
        if not generated_content:
            return GenerateResponse(success=False, error="Failed to generate content. Please try again.")

        timestamps = [Timestamp(time=ts['time'], title=ts['title']) for ts in generated_content.get('timestamps', [])]

        usage_remaining = None
        if user:
            await supabase_service.log_generation(user_id=user['id'], video_url=video_url, video_title=video_title)
            await supabase_service.increment_usage(user['id'])
            profile = await supabase_service.get_or_create_profile(user['id'], user['email'])
            if profile:
                usage_remaining = profile.get('usage_count', 0)

        return GenerateResponse(
            success=True,
            video_title=video_title,
            video_url=video_url,
            timestamps=timestamps,
            description=generated_content.get('description', ''),
            tags=generated_content.get('tags', []),
            hashtags=generated_content.get('hashtags', []),
            usage_remaining=usage_remaining
        )

    except Exception as e:
        logger.error(f"Error in generate endpoint: {e}", exc_info=True)
        return GenerateResponse(success=False, error=f"An error occurred: {str(e)}")


@api_router.get("/history", response_model=HistoryResponse)
async def get_history(authorization: Optional[str] = Header(None)):
    try:
        user = await get_user_from_token(authorization)
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        history_data = await supabase_service.get_user_history(user['id'])
        history_items = [HistoryItem(video_url=item['video_url'], video_title=item['video_title'], created_at=item['created_at']) for item in history_data]
        return HistoryResponse(success=True, history=history_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
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
        return {"success": True, "profile": {"email": profile['email'], "plan": profile['plan'], "usage_count": profile['usage_count']}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
