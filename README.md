# The Lost World Plateau

A bounded 2D ecosystem that evolves daily through user feedback — an experiment in agentic architecture.

Users submit requests, an agent pipeline prioritises and implements them, and the ecosystem evolves autonomously. The app is a vehicle for learning about agentic patterns, not a commercial product.

## Project Structure

```
frontend/    React app (TypeScript, Vite)
backend/     FastAPI app (Python, SQLite)
pipeline/    Agent pipeline (planned)
tests/       Test suites
contract.md  Architectural constitution (agent invariants)
```

## Getting Started

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## CI / Pipeline

Run the full check suite (lint, typecheck, test, build):

```bash
./scripts/pipeline.sh
```

### Git Hooks

Enable the pre-push hook so the pipeline runs before every push:

```bash
git config core.hooksPath .githooks
```

## Licence

Apache 2.0 — see [LICENSE](LICENSE).
