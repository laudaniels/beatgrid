from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="beatgrid")
    parser.add_argument(
        "command",
        nargs="?",
        help="Not implemented yet — see 'python -m beatgrid.gui.app' once M2 lands.",
    )
    parser.parse_args(argv)
    print("beatgrid CLI is not implemented yet (see PLAN.md milestones).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
