#!/usr/bin/env python3
"""Verify the Codex upload archive before a release publishes it.

A release that ships a plausible-looking but wrong archive is worse than one
that ships none, because the breakage surfaces in the Codex portal days later.
Every check here failed for real at least once: v1.25.0 shipped a manifest
whose `skills` path Codex rejected.
"""

from __future__ import annotations

import argparse
import json
import sys
from zipfile import BadZipFile, ZipFile

REQUIRED = (
    ".codex-plugin/plugin.json",
    "hooks/hooks.json",
    "scripts/tt-codex-hook.py",
    "scripts/tt-instructions.py",
    "scripts/tt-stats.py",
    "scripts/tt_adherence.py",
)


def failures(path, tag):
    """Return every reason the archive is unfit to publish, in report order."""
    problems = []
    try:
        archive = ZipFile(path)
    except (OSError, BadZipFile) as error:
        return [f"cannot open archive: {error}"]
    with archive:
        damaged = archive.testzip()
        if damaged:
            problems.append(f"corrupt entry: {damaged}")
        names = set(archive.namelist())
        problems.extend(f"missing required file: {name}" for name in REQUIRED if name not in names)
        if any(name.startswith("codex-skills/") for name in names):
            problems.append("repository-only codex-skills/ leaked into the archive")
        if ".codex-plugin/plugin.json" not in names:
            return problems
        try:
            manifest = json.loads(archive.read(".codex-plugin/plugin.json"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            problems.append(f"packaged manifest is not readable JSON: {error}")
            return problems

    expected = tag.lstrip("v")
    if manifest.get("version") != expected:
        problems.append(f"packaged version {manifest.get('version')!r} does not match tag {tag}")
    declared = manifest.get("skills")
    if not isinstance(declared, str) or not declared:
        problems.append("packaged manifest declares no skills path")
        return problems
    # Codex resolves `skills` inside the archive, so the declared root must
    # actually contain a skill rather than merely exist in the repository.
    root = declared.removeprefix("./").rstrip("/")
    if not any(name.startswith(f"{root}/") and name.endswith("/SKILL.md") for name in names):
        problems.append(f"declared skills root {declared!r} contains no SKILL.md in the archive")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="path to the built Codex archive")
    parser.add_argument("tag", help="release tag, for example v1.26.0")
    args = parser.parse_args(argv)
    problems = failures(args.archive, args.tag)
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"Codex archive is publishable for {args.tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
