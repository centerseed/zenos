from __future__ import annotations

import argparse
from pathlib import Path

from zenos.skills_installer import (
    DEFAULT_MANIFEST_SOURCE,
    format_summary,
    install_skills,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zenos-skills",
        description="Install or update ZenOS skills from the central release manifest.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser(
        "setup",
        help="Install or update ZenOS skills in a target skills directory.",
    )
    setup.add_argument(
        "--skills-dir",
        default="~/.codex/skills",
        help="Target skills directory. Default: ~/.codex/skills",
    )
    setup.add_argument(
        "--source",
        default=DEFAULT_MANIFEST_SOURCE,
        help="Release manifest URL, repo root, or manifest path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        results = install_skills(
            skills_dir=Path(args.skills_dir).expanduser(),
            source=args.source,
        )
        print(format_summary(results))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
