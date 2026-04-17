# YouTube SEO Generator - Backend

## Deploy FREE on Railway in 5 minutes

### Step 1 - Get your OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with sk-)
4. Add $5 credit - this will last for ~1000 video generations!

### Step 2 - Deploy to Railway (Free)
1. Go to https://railway.app and sign up with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Upload this folder as a GitHub repo, OR use "Deploy from local" option
4. Railway will auto-detect and build the project

### Step 3 - Add Environment Variables in Railway
In your Railway project → Variables tab, add:
```
OPENAI_API_KEY=sk-your-key-here
SUPABASE_URL=https://pyvgzxsnwqwsbyhwuubvb.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
```

### Step 4 - Get your Railway URL
- Railway gives you a free URL like: https://your-app.railway.app
- Update your Chrome extension's API_URL to this new URL

### Cost Estimate
- Railway hosting: FREE (up to 500 hours/month)
- OpenAI gpt-4o-mini: ~$0.0002 per generation (extremely cheap!)
- 100 videos/month ≈ $0.02 (2 cents!)

### Local Development
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
uvicorn server:app --reload --port 8001
```
