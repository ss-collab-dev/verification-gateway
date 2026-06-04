# Deploy Landing Page to GitHub Pages

## Quick Deploy (5 minutes)

### Option 1: GitHub Pages (Recommended)

1. **Create new repo:** `ss-collab-dev.github.io`
   ```bash
   cd /home/osboxes/.openclaw/workspace
   mkdir -p ss-collab-dev.github.io
   cd ss-collab-dev.github.io
   git init
   ```

2. **Copy landing page:**
   ```bash
   cp /home/osboxes/.openclaw/workspace/ai-agent-world/builds/cronoptimize/landing-page.html index.html
   ```

3. **Add and push:**
   ```bash
   git add index.html
   git commit -m "Deploy Verification Gateway landing page"
   git remote add origin git@github.com:ss-collab-dev/ss-collab-dev.github.io.git
   git push -u origin main
   ```

4. **Enable GitHub Pages:**
   - Go to repo Settings → Pages
   - Source: Deploy from branch
   - Branch: main, root folder
   - Save

5. **Live URL:** https://ss-collab-dev.github.io

### Option 2: Vercel (Faster, Custom Domain)

1. Go to vercel.com
2. Import GitHub repo: `verification-gateway`
3. Point root to `landing-page.html`
4. Deploy → Instant live URL
5. Add custom domain later if needed

**Live in 2 minutes!** ⚡

---

## After Deployment

- [ ] Update Twitter bio with landing page URL
- [ ] Add URL to GitHub repo description
- [ ] Include in all social media posts
- [ ] Add Google Analytics tracking code
- [ ] Set up beta signup form (Typeform/Google Forms)

