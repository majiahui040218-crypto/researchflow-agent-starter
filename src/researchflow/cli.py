"""Run or look up research tasks using `python -m researchflow.cli`."""

import argparse
import sys

from .service import load_research, run_research


def main() -> None:
    parser = argparse.ArgumentParser(description="ResearchFlow Agent")
    parser.add_argument("question", nargs="?", help="Technical research question")
    parser.add_argument("--task-id", help="Look up a previously saved task UUID")
    args = parser.parse_args()

    if args.task_id:
        result = load_research(args.task_id)
        if result is None:
            print("Task not found")
            sys.exit(1)
    else:
        if not args.question:
            parser.error("Enter a question, or use --task-id UUID")
        result = run_research(args.question)

    print(f"Mode: {result.mode}; task_id: {result.task_id}; status: {result.status}")
    if result.status == "failed":
        print(f"Error: {result.error_code}: {result.error_message}")
        print(f"Saved task: python -m researchflow.cli --task-id {result.task_id}")
        sys.exit(1)
    if result.status == "running":
        print("Task has no terminal outcome yet (may have been interrupted).")
        return

    print(result.state.get("report", ""))
    if result.state.get("warnings"):
        print("\nWarnings:")
        for warning in result.state["warnings"]:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
