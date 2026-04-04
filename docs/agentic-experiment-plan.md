# Agentic Architecture Experiment — Planning Document

## The Experiment

An experiment in agentic architecture: a lightweight app that evolves autonomously through user feedback. The core loop:

1. Users provide feedback through the app itself <!-- completed -->
2. Feedback is processed and prioritised by an agent pipeline <!-- completed -->
3. Agents generate and deploy the update <!-- completed -->
4. Users see changes and provide feedback the next day

The app is a vehicle for the experiment. The goal is to learn about agentic patterns, not to build a commercial product.

---

## The App: The Lost World Plateau

### Concept
A bounded 2D ecosystem — "The Lost World plateau" — that evolves daily through user requests. The hook is watching autonomous evolution in action, with a deliberate meta-reference to biological evolution. <!-- completed -->

### Day-One Scope
- **Rendering:** HTML Canvas <!-- completed -->
- **Ecosystem:** Constrained plateau with one terrain feature (water source) <!-- completed -->
- **Starting species:** Plants, herbivores, one predator <!-- completed -->
- **Behaviours:** Move, eat, reproduce, die <!-- completed -->
- **Energy system:** Eat to gain energy, move to spend it, reproduce costs energy <!-- completed -->
- **Feedback interface:** Simple text box ("What should we add or change?") <!-- completed -->
- Species characteristics beyond herbivore/carnivore/plant deferred to user requests

### Design Principles
- Immediately understandable — no onboarding, no learning curve <!-- completed -->
- Visibly improvable — obvious gaps that invite suggestions <!-- completed -->
- Fun to check back on — people return to see what changed
- The feedback mechanism itself is subject to evolution

---

## Technical Architecture

### Tech Stack
- **Frontend:** React (single-page app, HTML Canvas for ecosystem rendering) <!-- completed -->
- **Backend:** FastAPI (Python) <!-- completed -->
- **Vector DB:** ChromaDB <!-- completed -->
- **Local LLM runtime:** Ollama <!-- completed -->
- **Source control:** Git monorepo (frontend + backend + agent pipeline) <!-- completed -->

### Infrastructure
- **Development:** Windows desktop
- **Production:** Wiped MacBook M3 16GB, running as a dedicated server (clean OS, sleep disabled, ethernet)
- **Exposure:** Cloudflare Tunnel (no port forwarding needed) <!-- completed -->
- **Accepted risk:** Home internet or hardware failure takes the app offline; acceptable for an experiment

### Agent Ecosystem
- **Local models (Ollama, 7-8B on MacBook M3):** Cheap tasks — evil filtering, embedding generation, clustering, agent notes for queue <!-- completed -->
- **API models (Claude/GPT-4o):** Expensive tasks — code writing, code review <!-- completed -->
- **Orchestration:** Simple Python script with plugin pattern — each agent is a module with a standard interface (`run(input) → output`). No framework; YAGNI. Migrate to a framework later if complexity demands it. <!-- completed -->
- **Modularity:** Standard interface per agent step allows swapping models/providers without changing the pipeline <!-- completed -->

### Processing Split

**Submission-time (local, per request):**
- Evil filtering (local LLM) <!-- completed -->
- Embedding generation and clustering (ChromaDB) <!-- completed -->

**Batch-time (daily):**
- Prioritise clusters by request volume <!-- completed -->
- Write code (API model) <!-- completed -->
- Review code (different API model) <!-- completed -->
- Evil-detection deployment review
- Deploy <!-- completed -->

### Deployment Pipeline
1. Agent commits to feature branch (atomic per request) <!-- completed -->
2. Automated tests run (essential test suite + deterministic checks) <!-- completed -->
3. Review agent approves <!-- completed -->
4. Merge to main <!-- completed -->
5. Auto-deploy from main (git pull + process restart) <!-- completed -->

---

## Quality & Safety Guardrails

### Deployment Model
- **Goal:** Full autonomy with a human emergency brake
- **Commits:** Atomic per feature request <!-- completed -->
- **Deployments:** Batched (multiple atomic commits per deployment) <!-- completed -->
- **Rollback:** Reverse-chronological order within a batch; rolling back one commit means rolling back everything after it too
- **Emergency brake:** Stops current change, pauses future changes, offers option to roll back further

### Multi-Agent Review
- Agent 1 writes, Agent 2 reviews <!-- completed -->
- **Multi-model approach:** Different underlying models for writer and reviewer to avoid correlated blind spots
- **Modular design:** Agents/models can be swapped per role to test capabilities <!-- completed -->

### Sandboxing & Security
- Dedicated VM/container with no outbound access except via explicit proxy
- Proxy allowlists only: git remote, package registry, deployment target
- No SSH out, no arbitrary HTTP, no email, no unexpected DNS

### Architectural Constitution
- **Static contract file:** Unmodifiable by agents; read before planning any work. Defines invariants (e.g. "app must have a landing page," "all routes must be reachable," "user data must not be exposed") <!-- completed -->
- **Essential test suite:** Human-maintained only; runs regardless of what the app currently does <!-- completed -->
- **Constitutional amendment process:** Agents can flag "core purpose has shifted and the test suite is causing problems" via a ring-fenced communications channel. Humans approve or reject changes to the contract/test suite.
- **Ring-fenced comms channel:** Implementation TBD (Slack, email, or a dedicated page in the app) <!-- completed -->

### Code Quality
- Deterministic checks (linting, static analysis) + agentic review <!-- completed -->
- Specific linting/static analysis tooling TBD <!-- completed -->

### Observability & Degradation Detection

Leading indicators (in order of ease of detection):

1. Build/bundle size — logged per deployment <!-- completed -->
2. Lighthouse scores — automated runs post-deployment <!-- completed -->
3. Page load time / core web vitals — synthetic monitoring <!-- completed -->
4. Test execution time — trend tracking <!-- completed -->
5. Dependency count & vulnerability audit — automated CVE scanning <!-- completed -->
6. Code complexity metrics — cyclomatic complexity, duplication, file count <!-- completed -->
7. Error rate in production — requires real traffic <!-- completed -->

### Threshold Alerts (Two-Tier)
- **Hard thresholds:** Auto-pause the pipeline (e.g. Lighthouse below 60, build fails, CVE detected)
- **Soft thresholds:** Flag to ring-fenced comms channel for human review (e.g. bundle size up 20% over a week, complexity trending upward)

---

## Business Process

### Batch Cadence
- **Daily** — one batch per day, gives natural "episode" structure for blog posts <!-- completed -->
- Can be adjusted later if needed

### Prioritisation Pipeline
1. Reject evil/abusive requests (LLM filter) <!-- completed -->
2. Cluster remaining requests by similarity (embedding-based) <!-- completed -->
3. Prioritise clusters with the most requests <!-- completed -->
4. Upvote/downvote system — planned as a self-requested enhancement

### Cost Management
- **Primary cost:** LLM API calls only (~£1-5 per daily cycle)
- **Hosting cost:** Effectively zero — just electricity and internet
- **Daily cap:** £2 <!-- completed -->
- **Weekly cap:** £8 <!-- completed -->
- **Over-cap behaviour:** In-flight work pauses, remaining requests roll over to next day, status message displayed in the queue <!-- completed -->

---

## User Experience of the Feedback Loop

### Day-One UX
- **Submit:** Simple text box on the page <!-- completed -->
- **Acknowledgement:** Reference number returned on submission <!-- completed -->
- **Visibility:** Public queue showing all pending requests <!-- completed -->
- **Transparency:** Full agent decision-making exposed — why a request was picked, how it was implemented
- **Completion:** "Done" requests visible with agent notes on what was built <!-- completed -->
- **No notifications:** Users check back manually <!-- completed -->

### Planned Self-Requested Enhancements
- Patch notes / "naturalist's log" per deployment
- Ecosystem history timeline (how the plateau looked over time)

---

## Evaluation & Observability

### Day-One Metrics (Automated)
- **Deploy without breaking** — basic health check post-deployment <!-- completed -->
- **Request completion rate** — requests addressed vs. requests in batch
- **Code churn** — lines changed, files touched, percentage of codebase modified per cycle (git stats at PR level)
- Leading indicators from guardrails section (bundle size, Lighthouse, web vitals, etc.)

### V2 Enhancements
- User feedback sentiment analysis
- "Taste reviewer" agent assessment per cycle
- Request fidelity scoring (did the agent build what was asked for?)

### Scope & Drift Management
- **Contract file** explicitly constrains scope to ecosystem simulator <!-- completed -->
- If community consistently pushes beyond this boundary, agents flag via the constitutional amendment channel
- **Human decides** whether to relax constraints, fork into a separate mini-app, or hold the line
- Start constrained; loosening is easy, tightening after the fact is hard

---

## Legal & Ethical

### Users
- **Anonymous** — no accounts, no login <!-- completed -->
- Lowers GDPR/data protection surface (no PII) <!-- completed -->
- Reduces barrier to participation (helps cold-start)

### Input Filtering
- LLM filter on all user submissions before they enter the pipeline <!-- completed -->
- Rate limiting by IP/session token to prevent spam/flooding

### Intellectual Property
- User submissions treated as unowned suggestions (no claim on output)
- All generated code owned by Henry
- **Licence:** Apache 2.0 with a CONTRIBUTORS file convention <!-- completed -->
- AI-generated code copyrightability is legally unsettled; permissive licence sidesteps this

### Liability & Terms of Service
- Simple terms of service with "as-is, no warranty" disclaimer
- **Terms of service protected in the contract file** — agents cannot modify or remove it <!-- completed -->
- Dedicated evil-detection agent reviews each deployment and flags problematic output, feeding into the pause mechanism

### Privacy & Data Handling
- Lightweight privacy policy: minimal collection, no third-party sharing
- Store feedback submissions, basic session data, IP for rate limiting
- Raw feedback retained (revisit if volume becomes an issue)
- Retain data only as long as needed for processing (except raw feedback archive)

---

## User Acquisition & Community

### Strategy (Zero Budget)
- **Blog posts:** Weekly, capturing learnings and decisions — doubles as documentation and public visibility
- **Hacker News:** "Show HN" post when the loop is running end-to-end
- **Reddit:** Posts in relevant subreddits
- **LinkedIn:** Progress updates targeting professional network
- **Dev.to / Hashnode:** Cross-post blog content for built-in discovery
- **Twitter/X:** Short progress updates with screenshots/clips of the ecosystem evolving
- **The app itself:** Shareable by nature — "built by AI agents, guided by you"
- **Existing networks:** Reform Club and Citizens Advice connections for amplifying posts

### Cold-Start Mitigation
- Henry can be the sole user initially and still close the loop
- Real users make it more interesting but are not a prerequisite for the experiment to work

---

## Success Criteria

### Success Ladder
1. **Minimum:** Close the full loop end-to-end once (user feedback → agent pipeline → autonomous deployment)
2. **Good:** Develop clear, evidence-based opinions on agentic architecture patterns
3. **Great:** Produce a shareable write-up or demo useful in job conversations
4. **Stretch:** Open-source release that others can learn from or build on

### Cadence
- Meaningful milestone each month, aiming faster
- Weekly blog posts capturing learnings and decisions

### Failure Conditions
- Learning nothing
- Giving up before building a useful subset of the system
- It goes feral and destroys something meaningful

---

## Roadmap

### Month 1: Foundation — "Close the loop manually" - COMPLETE

**Week 1: Setup**
- Wipe MacBook, install clean OS (Ubuntu Server or macOS)
- Set up development environment on Windows desktop
- Create accounts: GitHub, Anthropic API, OpenAI API, Cloudflare
- Initialise monorepo, set up basic project structure <!-- completed -->

**Week 2: Build the app**
- React frontend with HTML Canvas ecosystem (plants, herbivores, predator, water source) <!-- completed -->
- FastAPI backend (serve app, accept feedback submissions, store in SQLite or similar) <!-- completed -->
- Basic feedback text box and queue display <!-- completed -->
- Deploy locally, expose via Cloudflare Tunnel <!-- completed -->

**Week 3: Build the pipeline**
- Install Ollama on MacBook, set up local model for filtering <!-- completed -->
- Set up ChromaDB for embeddings <!-- completed -->
- Build the agent plugin framework (standard interface) <!-- completed -->
- Wire up one API model for code writing <!-- completed -->
- Write the daily batch script (prioritise → write → deploy) <!-- completed -->

**Week 4: Close the loop**
- Submit own feedback requests
- Run the full pipeline end-to-end (manually triggered) <!-- completed -->
- Write the contract file and essential test suite <!-- completed -->
- First blog post: "What I'm building and why"
- **Milestone: Minimum success achieved ✅**

### Month 2: Autonomy — "Let it run unsupervised"

**Weeks 5-6: Guardrails**
- Add the review agent (second model) <!-- completed -->
- Implement the deployment pipeline (feature branch → tests → review → merge → auto-deploy) <!-- completed -->
- Set up deterministic checks (linting, basic tests) <!-- completed -->
- Implement emergency brake mechanism
- Add budget caps and over-cap behaviour <!-- completed -->

**Weeks 7-8: Observability and polish**
- Add day-one metrics (build size, Lighthouse, code churn tracking) <!-- completed -->
- Set up hard/soft threshold alerts
- Automate the daily batch via cron
- Add reference numbers and agent notes to the queue display <!-- completed -->
- Submit self-requested enhancements (naturalist's log, history timeline)
- **Milestone: Fully autonomous daily loop running**

### Month 3: Go public — "Show the world"

**Weeks 9-10: Harden for real users**
- Rate limiting and session tokens
- Terms of service and privacy policy in the app <!-- completed -->
- Evil-detection review agent
- Sandboxing review (proxy allowlisting, outbound restrictions)
- Stress-test with own adversarial requests

**Weeks 11-12: Launch and learn**
- "Show HN" post
- Reddit, LinkedIn, Dev.to, Twitter/X posts
- Cross-post blog content
- Monitor, observe, blog about what happens
- **Milestone: Real users submitting feedback and seeing agent-deployed changes**

---

## Open Questions

- Specific linting and static analysis tooling for code quality checks <!-- completed -->
- Ring-fenced comms channel implementation (Slack, email, or in-app?) <!-- completed -->
- Specific hard/soft threshold values for observability alerts
- Detailed contract file contents <!-- completed -->
