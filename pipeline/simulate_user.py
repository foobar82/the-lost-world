"""Entry point for the user emulation agent.

Generates synthetic user feedback from a simulated persona and optionally
submits it to the backend API.

Usage:
    python -m pipeline.simulate_user [--n N] [--persona NAME] [--dry-run]
                                     [--api-url URL] [--repo-path PATH]

Options:
    --n N           Number of feedback items to generate (default: 3)
    --persona NAME  Persona name from PERSONAS dict (default: curious_explorer)
    --dry-run       Generate and print items but do not submit or save trace
    --api-url URL   Backend API base URL (default: http://localhost:8000)
    --repo-path P   Path to the repo root (default: current directory)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow running as `python -m pipeline.simulate_user` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.agents.base import AgentInput
from pipeline.config import PIPELINE_CONFIG
from pipeline.simulator.persona import PERSONAS
from pipeline.simulator.user_simulator import UserSimulatorAgent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the user emulation agent")
    parser.add_argument("--n", type=int, default=3, help="Number of items to generate")
    parser.add_argument(
        "--persona",
        default="curious_explorer",
        choices=list(PERSONAS.keys()),
        help="Persona to use",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not submit or save")
    parser.add_argument(
        "--api-url", default="http://localhost:8000", help="Backend API base URL"
    )
    parser.add_argument(
        "--repo-path", default=".", help="Path to the repository root"
    )
    args = parser.parse_args()

    agent = UserSimulatorAgent()
    result = agent.run(
        AgentInput(
            data={
                "n_items": args.n,
                "persona_name": args.persona,
                "api_base_url": args.api_url,
                "repo_path": args.repo_path,
                "dry_run": args.dry_run,
            },
            context=PIPELINE_CONFIG,
        )
    )

    print(f"\n{'='*60}")
    print(f"Result: {result.message}")
    print(f"Tokens used: {result.tokens_used}")

    if result.data:
        submitted = result.data.get("submitted", [])
        skipped = result.data.get("skipped", [])
        reasoning = result.data.get("reasoning", "")

        if submitted:
            print(f"\nSubmitted ({len(submitted)}):")
            for item in submitted:
                print(f"  • {item}")

        if skipped:
            print(f"\nSkipped ({len(skipped)}):")
            for s in skipped:
                print(f"  • {s['item'][:80]} — {s['reason']}")

        if reasoning:
            print(f"\nReasoning:\n  {reasoning}")

    if not result.success:
        logger.error("Simulation failed: %s", result.message)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
