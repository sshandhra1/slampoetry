# SlamPoetryFabric — Setup Guide
One-time setup to make the site fully live and self-updating.

---

## Step 1 — Create a free Supabase project

1. Go to **supabase.com** → Sign up / Log in
2. Click **New project** → name it `slampoetry` → choose a region close to you (US West for SF)
3. Wait ~2 minutes for it to spin up
4. Go to **SQL Editor** → paste the contents of `supabase_schema.sql` → click **Run**
5. Go to **Project Settings → API** and copy:
   - **Project URL** (looks like `https://xxxx.supabase.co`)
   - **anon public** key
   - **service_role** key (keep this secret — only for GitHub Actions)

---

## Step 2 — Add your Supabase credentials to the frontend

Open `public/index.html` and find these two lines near the top of the `<script>`:

```js
const SUPABASE_URL  = 'YOUR_SUPABASE_URL';
const SUPABASE_ANON = 'YOUR_SUPABASE_ANON_KEY';
```

Replace with your actual values. The **anon key is safe to put here** — it's public by design and Supabase's Row Level Security controls what it can access.

---

## Step 3 — Push to GitHub

```bash
# In your terminal, from this project folder:
git init
git add .
git commit -m "Initial commit — SlamPoetryFabric"
git branch -M main

# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/slampoetry.git
git push -u origin main
```

---

## Step 4 — Add secrets to GitHub Actions

1. Go to your GitHub repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret** and add:
   - Name: `SUPABASE_URL` → Value: your Project URL
   - Name: `SUPABASE_SERVICE_KEY` → Value: your service_role key

The scraper will now automatically run every 30 minutes.

---

## Step 5 — Connect Netlify to GitHub (auto-deploy)

1. Go to **netlify.com** → Log in
2. Click **Add new site → Import an existing project → GitHub**
3. Select your `slampoetry` repo
4. Build settings:
   - **Build command**: *(leave empty)*
   - **Publish directory**: `public`
5. Click **Deploy site**

From now on: every time GitHub Actions updates the DB, the browser shows the new events **live** — no re-deploy needed. Netlify only needs to re-deploy if you change the HTML itself.

---

## How it works after setup

```
Every 30 min:
  GitHub Actions → runs scraper → upserts to Supabase DB

Any open browser tab:
  Supabase Realtime WebSocket → detects DB change → refreshes events instantly
```

No manual steps needed. Ever.

---

## Running the scraper manually (for testing)

```bash
cd scraper
pip install -r requirements.txt

export SUPABASE_URL="https://xxxx.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-key"

python collect_events.py
```
