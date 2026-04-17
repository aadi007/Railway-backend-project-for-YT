from supabase import create_client, Client
import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)

    async def verify_user(self, access_token: str) -> Optional[Dict]:
        try:
            user_response = self.client.auth.get_user(access_token)
            if user_response and user_response.user:
                return {'id': user_response.user.id, 'email': user_response.user.email}
            return None
        except Exception as e:
            logger.error(f"Error verifying user: {e}")
            return None

    async def get_or_create_profile(self, user_id: str, email: str) -> Optional[Dict]:
        try:
            response = self.client.table('profiles').select('*').eq('id', user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            new_profile = {'id': user_id, 'email': email, 'plan': 'free', 'usage_count': 0, 'created_at': datetime.utcnow().isoformat()}
            insert_response = self.client.table('profiles').insert(new_profile).execute()
            if insert_response.data and len(insert_response.data) > 0:
                return insert_response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting/creating profile: {e}")
            return None

    async def increment_usage(self, user_id: str) -> bool:
        try:
            response = self.client.table('profiles').select('usage_count').eq('id', user_id).execute()
            if not response.data:
                return False
            current_usage = response.data[0]['usage_count']
            self.client.table('profiles').update({'usage_count': current_usage + 1}).eq('id', user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
            return False

    async def log_generation(self, user_id: str, video_url: str, video_title: str) -> bool:
        try:
            log_entry = {'user_id': user_id, 'video_url': video_url, 'video_title': video_title, 'created_at': datetime.utcnow().isoformat()}
            self.client.table('generation_logs').insert(log_entry).execute()
            return True
        except Exception as e:
            logger.error(f"Error logging generation: {e}")
            return False

    async def get_user_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        try:
            response = self.client.table('generation_logs').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return []
