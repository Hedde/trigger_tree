#!/usr/bin/env python3
"""Print concise, client-aware instruction-maintenance tips."""

import argparse
import os
from pathlib import Path


def markdown_lines(path):
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError):
        return 0


def has_paths_frontmatter(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return True
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---", 4)
    return end >= 0 and any(line.strip().startswith("paths:") for line in text[4:end].splitlines())


def claude_tips(root):
    tips = [
        "Run /memory periodically and remove stale or contradictory auto-memory entries; memory is editable context, not an enforced source of truth."
    ]
    instruction_files = [
        path for path in (root / "CLAUDE.md", root / ".claude" / "CLAUDE.md") if path.is_file()
    ]
    if not instruction_files:
        tips.append(
            "Add a project CLAUDE.md with only durable commands, conventions, and architecture facts you repeatedly need to explain."
        )
    for path in instruction_files:
        count = markdown_lines(path)
        if count > 200:
            tips.append(
                f"Trim {path.relative_to(root)} ({count} lines): Anthropic recommends targeting under 200 lines and moving specialized guidance to scoped rules or skills."
            )
            break
    rules_dir = root / ".claude" / "rules"
    unscoped = (
        sorted(
            path.relative_to(root).as_posix()
            for path in rules_dir.rglob("*.md")
            if path.is_file() and not has_paths_frontmatter(path)
        )
        if rules_dir.is_dir()
        else []
    )
    if unscoped:
        examples = ", ".join(unscoped[:2])
        suffix = " …" if len(unscoped) > 2 else ""
        tips.append(
            f"Review {len(unscoped)} always-loaded rule file(s) for path scoping ({examples}{suffix}); unconditional rules consume context in every session."
        )
    return tips[:4]


def codex_tips(root):
    agents = root / "AGENTS.md"
    tips = []
    if not agents.is_file():
        tips.append(
            "Add AGENTS.md with repository navigation, build/test commands, conventions, and non-obvious constraints that Codex cannot infer reliably."
        )
    else:
        tips.append(
            "Review AGENTS.md after architecture or workflow changes so persistent Codex instructions do not drift from the repository."
        )
        text = agents.read_text(encoding="utf-8", errors="replace").lower()
        if not any(token in text for token in ("test", "check", "verify", "ci")):
            tips.append(
                "Add exact verification commands to AGENTS.md; reproducible environment and test instructions reduce avoidable agent errors."
            )
    tips.append(
        "Keep agent-facing indexes and commands executable and inspectable; use trigger-tree suggestions for evidence-backed navigation gaps."
    )
    return tips[:4]


def tips_for(client, root):
    root = Path(root).resolve()
    return claude_tips(root) if client == "claude" else codex_tips(root)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, choices=("claude", "codex"))
    parser.add_argument("--project", default=os.getcwd())
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    tips = tips_for(args.client, args.project)
    print(f"🌳 {args.client.title()} maintenance tips — review only; nothing was changed.")
    for number, tip in enumerate(tips, 1):
        print(f"{number}. {tip}")


if __name__ == "__main__":
    main()
