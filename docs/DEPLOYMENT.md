# Deployment Guide

Step-by-step instructions for deploying the Lost World Plateau simulator on a
factory-clean MacBook running macOS.

---

## Prerequisites

You need three tools installed before anything else: **Homebrew** (a macOS
package manager), **Python 3**, and **Node.js**. If you already have any of
these, skip the corresponding step.

### Step 1 — Install Homebrew

Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter) and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen prompts. When it finishes, it will print instructions to
add Homebrew to your PATH. Run the commands it shows you — they look like this
(the exact path depends on your Mac):

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Verify it works:

```bash
brew --version
```

You should see output like `Homebrew 4.x.x`.

### Step 2 — Install Python 3

```bash
brew install python
```

Verify:

```bash
python3 --version
```

You should see `Python 3.12.x` or later.

### Step 3 — Install Node.js

```bash
brew install node
```

Verify both `node` and `npm` are available:

```bash
node --version
npm --version
```

You should see `v22.x.x` (or later) and `10.x.x` (or later).

### Step 4 — Install Git (if needed)

macOS may prompt you to install Xcode Command Line Tools the first time you use
`git`. If `git --version` shows an error, run:

```bash
xcode-select --install
```

Follow the dialog that appears, then confirm with:

```bash
git --version
```

---

## Getting the Code

### Step 5 — Clone the repository

```bash
cd ~
git clone <REPOSITORY_URL> the-lost-world
cd the-lost-world
```

Replace `<REPOSITORY_URL>` with the actual Git URL for this project.

---

## Setting Up the Backend

### Step 6 — Create a Python virtual environment

```bash
cd ~/the-lost-world/backend
python3 -m venv venv
```

### Step 7 — Activate the virtual environment

```bash
source venv/bin/activate
```

Your terminal prompt should now start with `(venv)`.

> **Note:** You will need to run this `source` command every time you open a new
> terminal window and want to work with the backend.

### Step 8 — Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, SQLAlchemy, and everything else the backend
needs.

### Step 9 — Verify the backend starts

```bash
uvicorn app.main:app --reload
```

Open your browser and go to `http://localhost:8000/api/health`. You should see:

```json
{"status": "ok"}
```

Press `Ctrl + C` in the terminal to stop the server.

---

## Setting Up the Frontend

### Step 10 — Install JavaScript dependencies

```bash
cd ~/the-lost-world/frontend
npm install
```

### Step 11 — Verify the frontend starts

```bash
npm run dev
```

Open your browser and go to `http://localhost:5173`. You should see the Lost
World Plateau interface. The frontend automatically proxies `/api` requests to
the backend at `localhost:8000`, so you will need both running during
development.

Press `Ctrl + C` to stop the dev server.

---

## Running in Development Mode

Development mode gives you hot-reloading for both frontend and backend. Open
**two** terminal windows:

**Terminal 1 — Backend:**

```bash
cd ~/the-lost-world/backend
source venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 — Frontend:**

```bash
cd ~/the-lost-world/frontend
npm run dev
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Health check: `http://localhost:8000/api/health`

---

## Running in Production Mode

Production mode builds the frontend into static files and serves everything
(API + UI) from a single server on port 8000.

### Step 12 — Activate the virtual environment

```bash
cd ~/the-lost-world/backend
source venv/bin/activate
```

### Step 13 — Run the deploy script

```bash
cd ~/the-lost-world
./deploy.sh
```

This script:

1. Runs `npm ci && npm run build` in `frontend/` to create an optimised
   production build
2. Sets the `LOST_WORLD_STATIC` environment variable so the backend knows where
   to find the built files
3. Starts Uvicorn on port 8000, serving both the API and the frontend

The app is now available at `http://localhost:8000`.

---

## Exposing to the Internet with Cloudflare Tunnel (Optional)

If you want the app accessible from a public URL (e.g.
`https://lostworld.yourdomain.com`), you can use Cloudflare Tunnel. This
requires a free Cloudflare account and a domain whose DNS is managed by
Cloudflare.

### Step 14 — Install cloudflared

```bash
brew install cloudflared
```

### Step 15 — Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser window. Log into your Cloudflare account and authorise the
machine. A certificate is saved to `~/.cloudflared/`.

### Step 16 — Create a tunnel

```bash
cloudflared tunnel create lost-world
```

Note the **tunnel ID** (a UUID like `abcd1234-5678-...`) printed in the output.
You will need it in the next step.

### Step 17 — Configure the tunnel

Create the file `~/.cloudflared/config.yml` with the following content. Replace
the two placeholders with your own values:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/<YOUR_USERNAME>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: lostworld.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

- Replace `<TUNNEL_ID>` with the UUID from Step 16.
- Replace `<YOUR_USERNAME>` with your macOS username (run `whoami` to check).
- Replace `lostworld.yourdomain.com` with your chosen subdomain.

### Step 18 — Create the DNS record

```bash
cloudflared tunnel route dns lost-world lostworld.yourdomain.com
```

This automatically adds a CNAME record in Cloudflare DNS pointing your
subdomain to the tunnel.

### Step 19 — Start the tunnel

```bash
cloudflared tunnel run lost-world
```

Visit `https://lostworld.yourdomain.com` — you should see the app served over
HTTPS.

### Step 20 — (Optional) Run the tunnel as a background service

To keep the tunnel running after you close Terminal, install it as a macOS
launch daemon:

```bash
sudo cloudflared service install
sudo launchctl start com.cloudflare.cloudflared
```

The tunnel will now start automatically on boot.

---

## Database

The backend uses **SQLite** by default. The database file (`lost_world.db`) is
created automatically in the `backend/` directory the first time the server
starts. No setup is needed.

To use a different database, set the `DATABASE_URL` environment variable before
starting the server:

```bash
export DATABASE_URL="sqlite:///./my_custom.db"
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./lost_world.db` | Database connection string |
| `LOST_WORLD_STATIC` | *(unset)* | Path to built frontend `dist/` directory. Set automatically by `deploy.sh` in production |

---

## Troubleshooting

**`command not found: brew`** — Homebrew is not in your PATH. Re-run the PATH
commands printed at the end of the Homebrew installer (see Step 1).

**`command not found: python3`** — Python is not installed or not in your PATH.
Run `brew install python` and open a new terminal window.

**`command not found: node` or `command not found: npm`** — Node.js is not
installed. Run `brew install node` and open a new terminal window.

**`No module named 'app'`** — You are running `uvicorn` from the wrong
directory. Make sure you are in `the-lost-world/backend/` (not `backend/app/`).

**`Error: Cannot find module ...`** — Frontend dependencies are missing. Run
`npm install` in the `frontend/` directory.

**Port 8000 already in use** — Another process is using the port. Find it with
`lsof -i :8000` and stop it, or specify a different port:
`uvicorn app.main:app --port 8001`.

**Virtual environment not activated** — If `pip install` puts packages in the
wrong place or `uvicorn` is not found, make sure you ran
`source venv/bin/activate` first. Your prompt should show `(venv)`.
