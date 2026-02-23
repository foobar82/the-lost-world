# Week 2: Build the App — Implementation Plan for Claude Code

## Context

This plan is for Claude Code running on a Windows desktop. The target is a monorepo already initialised on GitHub. The production environment is a MacBook M3 (macOS, clean install) exposed via Cloudflare Tunnel.

The app is "The Lost World Plateau" — a 2D ecosystem simulator that evolves daily through user feedback. See the main planning document for full context.

---

## Phase 1: Project Scaffolding

### 1.1 Monorepo Structure

```
lost-world/
├── frontend/          # React app
├── backend/           # FastAPI app
├── pipeline/          # Agent pipeline (week 3)
├── contract.md        # Architectural constitution (week 4)
├── tests/
│   ├── frontend/
│   ├── backend/
│   └── essential/     # Human-maintained essential tests (week 4)
├── .gitignore
├── README.md
├── LICENSE            # Apache 2.0
└── CONTRIBUTORS.md
```

### 1.2 Frontend Setup

```bash
cd frontend
npx create-react-app . --template typescript
# Or Vite if preferred:
# npm create vite@latest . -- --template react-ts
```

Use TypeScript from the start — it provides the kind of static checking that helps agents write safer code later.

### 1.3 Backend Setup

```bash
cd backend
python -m venv venv
pip install fastapi uvicorn sqlalchemy aiosqlite
```

Create a minimal FastAPI app with:
- SQLite database (simple, no external DB server needed)
- CORS middleware configured for the frontend

---

## Phase 2: The Ecosystem (Frontend)

### 2.1 Canvas Component

Create a React component that renders the plateau using HTML Canvas.

**Specifications:**
- Canvas fills the main viewport area (responsive, but a fixed logical world size e.g. 800x600)
- Background: green plateau with a distinct boundary (cliffs/edges to convey "bounded world")
- One water source rendered as a blue area near the centre

### 2.2 Entity System

Implement a simple entity system with three species:

**Plants:**
- Static position, randomly placed at initialisation
- Reproduce slowly (spawn a new plant nearby at a random interval)
- Have energy that depletes over time; die when energy reaches zero
- Replenish energy passively (photosynthesis)

**Herbivores:**
- Move randomly within the plateau bounds
- Seek nearby plants to eat (gain energy)
- Reproduce when energy exceeds a threshold (costs energy)
- Die when energy reaches zero

**Predators:**
- Move randomly, faster than herbivores
- Seek nearby herbivores to eat (gain energy)
- Reproduce when energy exceeds a threshold (costs energy)
- Die when energy reaches zero

**Shared entity properties:**
- Position (x, y)
- Energy (float, 0-100)
- Species type
- Visual representation (simple shapes: green circles for plants, brown circles for herbivores, red triangles for predators)

### 2.3 Simulation Loop

- Use `requestAnimationFrame` for rendering
- Run simulation ticks at a fixed rate (e.g. 10 ticks per second, decoupled from frame rate)
- Each tick: update all entities (move, seek food, eat, reproduce, die)
- Simple collision/proximity detection for eating (distance-based, not pixel-perfect)

### 2.4 Initial Parameters

Start with balanced values that produce a visibly active but stable ecosystem:
- 30 plants, 15 herbivores, 5 predators
- Plant reproduction rate: ~1 new plant per 5 seconds per plant (capped by density)
- Herbivore/predator energy drain: ~1 per second while moving
- Eating restores 30 energy
- Reproduction threshold: 70 energy, costs 40 energy

These will need tuning — the goal is "visibly alive" not "perfectly balanced."

---

## Phase 3: The Backend

### 3.1 Data Model

**Feedback submissions table:**
- `id` (auto-increment integer)
- `reference` (unique string, e.g. "LW-001")
- `content` (text — the user's request)
- `status` (enum: pending, in_progress, done, rejected)
- `agent_notes` (text, nullable — populated when processed)
- `created_at` (datetime)
- `updated_at` (datetime)

### 3.2 API Endpoints

```
POST /api/feedback
  Body: { "content": "Add fish to the water" }
  Returns: { "reference": "LW-042", "status": "pending" }

GET /api/feedback
  Returns: list of all feedback items (newest first)
  Query params: ?status=pending|in_progress|done|rejected

GET /api/feedback/{reference}
  Returns: single feedback item by reference number
```

### 3.3 Reference Number Generation

Sequential with prefix: LW-001, LW-002, etc. Simple and readable.

---

## Phase 4: Feedback UI

### 4.1 Layout

Single page with two main areas:
- **Left/top (primary):** The ecosystem canvas
- **Right/bottom (secondary):** Feedback panel

On mobile, stack vertically (canvas on top, feedback below).

### 4.2 Feedback Panel Components

**Submit box:**
- Simple text input + submit button
- On submit: POST to `/api/feedback`, display returned reference number
- Clear input after successful submission
- Brief inline confirmation: "Submitted as LW-042"

**Request queue:**
- List of all feedback items from GET `/api/feedback`
- Each item shows: reference number, content (truncated), status badge, agent notes (if done)
- Status badges: Pending (grey), In Progress (amber), Done (green), Rejected (red)
- Poll for updates every 30 seconds (or on page focus)

### 4.3 Visual Design

The app should feel like a naturalist's field station — warm, slightly vintage, inviting curiosity. Not slick SaaS; more like a research tool you'd find in a Victorian explorer's tent.

Suggestions for Claude Code:
- Warm colour palette (parchment, forest green, earth tones)
- A serif or slab-serif font for headings (something with character)
- The canvas should feel like looking through a window at the plateau
- Minimal chrome — let the ecosystem be the star

---

## Phase 5: Local Deployment

### 5.1 Development Server

- Frontend: `npm start` (or `npm run dev` for Vite) on port 3000
- Backend: `uvicorn main:app --reload` on port 8000
- Frontend proxies API requests to backend (configure in package.json or vite.config)

### 5.2 Production Build (for MacBook)

Create a simple deployment script (`deploy.sh`) that:
1. Builds the React frontend (`npm run build`)
2. Serves the static build via FastAPI (mount as static files)
3. Runs uvicorn on a single port

This keeps production simple — one process, one port, Cloudflare Tunnel points at it.

### 5.3 Cloudflare Tunnel

Document the setup steps (not automated by Claude Code):
1. Install `cloudflared` on the MacBook
2. Authenticate with Cloudflare
3. Create a tunnel pointing to `localhost:8000`
4. Configure DNS (e.g. `lostworld.yourdomain.com`)

---

## Phase 6: Validation

### 6.1 Manual Testing Checklist

- [ ] Ecosystem renders and runs visibly (creatures moving, eating, reproducing, dying)
- [ ] Ecosystem is stable over 5 minutes (doesn't collapse to extinction or explode)
- [ ] Feedback text box submits successfully and returns a reference number
- [ ] Feedback appears in the queue with "pending" status
- [ ] Queue refreshes and shows updated items
- [ ] Layout works on desktop and mobile
- [ ] App loads in under 3 seconds

### 6.2 Known Gaps (Intentional)

These are NOT in scope for week 2:
- No agent pipeline (week 3)
- No contract file or essential tests (week 4)
- No filtering or embedding of submissions (week 3)
- No authentication or rate limiting (month 3)
- No terms of service or privacy policy (month 3)
- Feedback status will remain "pending" — nothing processes it yet

---

## Notes for Claude Code

- Use TypeScript throughout (frontend and consider type hints in Python backend)
- Keep the code clean and well-commented — agents will be modifying this autonomously later
- Favour simplicity over cleverness; readability matters more than optimisation
- The ecosystem parameters will need tuning; make them easily configurable (constants file or config object)
- The visual design should be distinctive and warm, not generic — see Phase 4.3
- Commit atomically: scaffolding, then ecosystem, then backend, then UI, then deployment
