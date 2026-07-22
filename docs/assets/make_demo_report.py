#!/usr/bin/env python3
"""Regenerate demo-report.html from fixed synthetic telemetry (`make demo-report`).

Builds a throwaway project with a small docs tree and three weeks of hand-written
history events (fixed timestamps — deterministic by construction), runs the real
tt-report.py against it, labels the output as an example, and writes the result to
the repository root for the website to link.
"""

import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "demo-report.html")

FILES = {
    "CLAUDE.md": "# demo-project\n\nStart at [the docs router](docs/README.md).\n",
    "docs/README.md": (
        "# Documentation router\n\n- [Design](design/index.md)\n"
        "- [Database](database/index.md)\n- [Operations](operations/index.md)\n"
    ),
    "docs/design/index.md": (
        "# Design\n\n- [Principles](principles.md)\n- [UI patterns](ui-patterns.md)\n"
    ),
    "docs/design/principles.md": "# Design principles\n\nClarity over cleverness.\n",
    "docs/design/ui-patterns.md": "# UI patterns\n\nButtons, forms, and empty states.\n",
    "docs/design/accessibility.md": "# Accessibility\n\nContrast and keyboard rules.\n",
    "docs/database/index.md": "# Database\n\n- [Migrations](migrations.md)\n",
    "docs/database/migrations.md": "# Migrations\n\nOne change per migration.\n",
    "docs/database/principles.md": "# Database principles\n\nTenant isolation first.\n",
    "docs/operations/index.md": "# Operations\n\n- [Runbooks](runbooks/rollback.md)\n",
    "docs/operations/runbooks/rollback.md": "# Rollback\n\nRevert, verify, announce.\n",
    "docs/legacy/old-api.md": "# Old API\n\nSuperseded; kept for history.\n",
}

READS = [
    ("docs/design/ui-patterns.md", 30),
    ("docs/design/principles.md", 22),
    ("docs/database/migrations.md", 18),
    ("docs/README.md", 10),
    ("docs/design/index.md", 9),
    ("docs/database/index.md", 8),
    ("docs/database/principles.md", 7),
    ("docs/operations/runbooks/rollback.md", 6),
    ("docs/design/accessibility.md", 2),
]

PROMPTS = [
    "style the buttons on the settings page",
    "add a tenant_id migration",
    "why is the deploy failing?",
    "tighten the empty states on the dashboard",
    "review the rollback runbook",
]

DAYS = (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21)


def build_events():
    events = []
    counter = 0
    for index, day in enumerate(DAYS):
        session = f"demo-{index + 1:02d}"
        stamp = f"2026-07-{day:02d}T09:00:00Z"
        events.append({"t": "session", "ts": stamp, "session": session, "source": "startup"})
        events.append(
            {
                "t": "prompt",
                "ts": f"2026-07-{day:02d}T09:01:00Z",
                "session": session,
                "prompt": PROMPTS[index % len(PROMPTS)],
            }
        )
        if day in (5, 11, 17):
            events.append(
                {
                    "t": "scan",
                    "ts": f"2026-07-{day:02d}T09:02:00Z",
                    "session": session,
                    "tool": "Grep",
                    "path": "docs/database",
                }
            )
    for path, total in READS:
        for occurrence in range(total):
            day = DAYS[occurrence % len(DAYS)]
            session = f"demo-{(occurrence % len(DAYS)) + 1:02d}"
            counter += 1
            events.append(
                {
                    "t": "read",
                    "ts": f"2026-07-{day:02d}T{10 + occurrence % 8:02d}:{occurrence % 60:02d}:00Z",
                    "session": session,
                    "tool": "Read",
                    "path": path,
                    "agent": "Explore" if occurrence % 5 == 4 else "main",
                    "tool_use_id": f"demo-{counter:04d}",
                }
            )
    events.append(
        {
            "t": "note",
            "ts": "2026-07-12T12:00:00Z",
            "session": "demo-06",
            "text": "sharpened the design router",
        }
    )
    events.sort(key=lambda event: (event["ts"], event.get("tool_use_id", "")))
    return events


def main():
    import json

    workdir = tempfile.mkdtemp(prefix="tt-demo-report-")
    try:
        for relative, content in FILES.items():
            target = os.path.join(workdir, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(content)
        telemetry = os.path.join(workdir, ".trigger-tree")
        os.makedirs(telemetry)
        with open(os.path.join(telemetry, "history.jsonl"), "w", encoding="utf-8") as handle:
            for event in build_events():
                handle.write(json.dumps(event) + "\n")
        env = {key: value for key, value in os.environ.items() if not key.startswith("TT_")}
        env["TT_PROJECT_DIR"] = workdir
        env.pop("CLAUDE_PROJECT_DIR", None)
        subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "tt-report.py"), "--client", "claude"],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        html = open(os.path.join(telemetry, "report.html"), encoding="utf-8").read()
        banner = (
            "</h1><p class=note><b>Example report</b> — generated from synthetic demo "
            "data so you can see the full format. Real reports are produced locally by "
            "<code>/tt insights</code> and never leave your machine.</p>"
        )
        assert "</h1>" in html and "synthetic demo" not in html
        html = html.replace("</h1>", banner, 1)
        with open(OUT, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(OUT)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
