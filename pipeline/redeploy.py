"""Manual deployer trigger — re-run the deploy step from a saved pipeline output JSON.

Usage:
    python -m pipeline.redeploy <path-to-output.json>
    python -m pipeline.redeploy <path-to-output.json> --force   # skip reviewer check
    cat output.json | python -m pipeline.redeploy -             # read from stdin
"""

import argparse
import json
import sys

from .agents.base import AgentInput
from .agents.deployer_agent import DeployerAgent
from .config import PIPELINE_CONFIG


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-run the deployer agent using a saved pipeline output JSON.",
    )
    parser.add_argument(
        "input",
        metavar="FILE",
        help="Path to the pipeline output JSON file, or '-' to read from stdin.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Deploy even if the reviewer did not approve.",
    )
    args = parser.parse_args()

    # Load JSON
    if args.input == "-":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            print(f"error: failed to parse JSON from stdin: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(args.input) as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            print(f"error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as exc:
            print(f"error: failed to parse JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    # Validate reviewer approval
    reviewer = payload.get("reviewer", {})
    verdict = reviewer.get("verdict", "")
    if verdict != "approve" and not args.force:
        print(
            f"error: reviewer verdict is '{verdict}', not 'approve'. "
            "Use --force to deploy anyway.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Extract writer data
    writer = payload.get("writer", {})
    changes = writer.get("changes", [])
    if not changes:
        print("error: no changes found in writer output.", file=sys.stderr)
        sys.exit(1)

    writer_data = {
        "changes": changes,
        "summary": writer.get("summary", "Manual redeploy"),
        "reasoning": writer.get("reasoning", ""),
    }

    # Run deployer
    cfg = dict(PIPELINE_CONFIG)
    agent_input = AgentInput(data=writer_data, context=cfg)
    output = DeployerAgent().run(agent_input)

    # Report results
    data = output.data or {}
    print(f"branch:   {data.get('branch', '(none)')}")
    print(f"deployed: {data.get('deployed', False)}")
    print(f"message:  {output.message}")

    if data.get("pipeline_stdout"):
        print("\n--- pipeline stdout ---")
        print(data["pipeline_stdout"])

    if data.get("pipeline_stderr"):
        print("\n--- pipeline stderr ---")
        print(data["pipeline_stderr"])

    if data.get("deploy_output"):
        print("\n--- deploy output ---")
        print(data["deploy_output"])

    sys.exit(0 if output.success else 1)


if __name__ == "__main__":
    main()
