# 🚀 Free Cloud Deployment Guide (AtlasRec)

AtlasRec includes a ready-to-run **All-in-One Cloud Dockerfile** ([`Dockerfile`](../Dockerfile)) and **Auto-Bootstrap Engine** ([`scripts/live_server.py`](../scripts/live_server.py)) that automatically downloads the 20,500-product Amazon dataset, trains the `item_cf` and `popularity` recommendation models, seeds the SQLite database, and starts both the **FastAPI ML Backend** and **Next.js 15 Storefront** on first boot.

---

## 🥇 Option 1: Hugging Face Spaces (100% Free Forever · 16 GB RAM · 2 vCPU · Recommended)

Because AtlasRec serves **20,500+ products** and **in-memory Collaborative Filtering / FAISS models**, **Hugging Face Spaces (Docker SDK)** is the best free host on the internet (`16 GB RAM` vs `512 MB` on Render).

### 3-Minute Setup Steps:
1. Create a free account at [https://huggingface.co/spaces](https://huggingface.co/spaces) and click **"Create new Space"**.
2. Configure your Space:
   - **Space name:** `atlasrec`
   - **Select the Space SDK:** Choose **`Docker`** $\rightarrow$ **`Blank`**.
   - **Space Hardware:** `CPU basic · 2 vCPU · 16 GB · FREE`.
   - **Visibility:** `Public`.
3. Connect or push your GitHub repository to the Space:
   ```powershell
   git remote add hf https://huggingface.co/spaces/<YOUR_HF_USERNAME>/atlasrec
   git push hf main
   ```
   *(Note: If Hugging Face prompts for a `README.md` YAML header, add the 6-line Space metadata block at the top of `README.md` when pushing to `hf`, or use GitHub Actions sync).*
4. **Done!** Hugging Face will automatically build [`Dockerfile`](../Dockerfile), run [`scripts/start-cloud.sh`](../scripts/start-cloud.sh), bootstrap the 20,500-product catalog, and give you a live URL:
   `https://<YOUR_HF_USERNAME>-atlasrec.hf.space`

---

## 🥈 Option 2: Vercel (Frontend) + Hugging Face / Render (Backend)

If you want your frontend hosted on a `.vercel.app` domain (`https://atlasrec.vercel.app`) backed by your cloud API:

1. **Deploy the Backend first** using Option 1 (Hugging Face Spaces) or Option 3 (Render.com) and copy your backend URL (e.g., `https://<YOUR_HF_USERNAME>-atlasrec.hf.space`).
2. Go to [https://vercel.com/new](https://vercel.com/new) and import **`Tanvir284/atlasrec-personalized-recommendation-engine`**.
3. Set the following in Vercel Project Settings:
   - **Root Directory:** `apps/web`
   - **Environment Variable:**
     - Name: `API_INTERNAL_URL`
     - Value: `https://<YOUR_BACKEND_URL>` *(no trailing slash)*
4. Click **Deploy**! Next.js will proxy all `/api/v1/*` requests to your backend seamlessly with full session cookie and CSRF support.

---

## 🥉 Option 3: One-Click Render.com Blueprint ([`render.yaml`](../render.yaml))

1. Go to [https://dashboard.render.com/blueprints](https://dashboard.render.com/blueprints) and click **"New Blueprint Instance"**.
2. Connect your GitHub repository: `https://github.com/Tanvir284/atlasrec-personalized-recommendation-engine`.
3. Render will automatically detect [`render.yaml`](../render.yaml) and deploy the Docker service.
