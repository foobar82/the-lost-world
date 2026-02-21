# Deployment Guide

## Development

Run the frontend and backend separately during development:

```bash
# Terminal 1 — Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend
npm run dev
```

- Frontend runs on `http://localhost:5173` (Vite dev server)
- Backend runs on `http://localhost:8000`
- Vite proxies `/api` requests to the backend automatically (configured in `vite.config.ts`)

## Production

A single script builds the frontend and starts the server on one port:

```bash
./deploy.sh
```

This:
1. Runs `npm ci && npm run build` in `frontend/`
2. Sets `LOST_WORLD_STATIC` to the built `dist/` directory
3. Starts uvicorn on port 8000, serving both the API and the static frontend

The app is then available at `http://localhost:8000`.

## Cloudflare Tunnel (MacBook production server)

The production MacBook is exposed to the internet via Cloudflare Tunnel. No port forwarding is needed.

### 1. Install cloudflared

```bash
# macOS (Homebrew)
brew install cloudflared

# Or download directly
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
```

### 2. Authenticate

```bash
cloudflared tunnel login
```

This opens a browser to authenticate with your Cloudflare account and authorises the machine.

### 3. Create a tunnel

```bash
cloudflared tunnel create lost-world
```

Note the tunnel ID (a UUID) printed in the output.

### 4. Configure the tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/<you>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: lostworld.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

### 5. Set up DNS

```bash
cloudflared tunnel route dns lost-world lostworld.yourdomain.com
```

This creates a CNAME record in Cloudflare DNS pointing to your tunnel.

### 6. Run the tunnel

```bash
cloudflared tunnel run lost-world
```

To run as a background service on macOS:

```bash
sudo cloudflared service install
sudo launchctl start com.cloudflare.cloudflared
```

### 7. Verify

Visit `https://lostworld.yourdomain.com` — you should see the app served over HTTPS via Cloudflare.
