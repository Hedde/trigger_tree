"""End-to-end regression guard: the watcher must pick up events appended by a
SEPARATE process (exactly how the real hooks write) — not just in-process."""
import json
import os
import re
import subprocess
import sys
import time

from conftest import SCRIPTS


def test_watcher_tails_events_from_another_process(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))

    watcher = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPTS, "tt-watch.py"), "--seconds", "2.5"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        encoding="utf-8", errors="replace",  # Windows pipes default to cp1252
    )
    time.sleep(0.8)
    event = json.dumps({"session_id": "e2e", "tool_name": "Read",
                        "tool_input": {"file_path": str(tmp_path / "docs" / "a.md")}})
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "tt-log.py"), "read"],
                   input=event, encoding="utf-8", env=env, check=True)
    out, _ = watcher.communicate(timeout=30)
    assert watcher.returncode == 0

    plain = re.sub(r"\x1b\[[0-9;]*m", "", out)
    frames = plain.split("--frame--")
    assert "0 reads" in frames[0]                      # started empty
    assert "1 reads" in frames[-2] and "a.md" in frames[-2]  # picked up the external append


def test_bash_lookup_then_read_improves_live_measurement_iteratively(tmp_path):
    """Transcript-level proof: discovery becomes a scan before a file is read."""
    docs = tmp_path / "docs" / "ui"
    docs.mkdir(parents=True)
    target = docs / "empty-states.md"
    target.write_text("# Empty states\n")
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))

    watcher = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPTS, "tt-watch.py"), "--seconds", "3.4"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        encoding="utf-8", errors="replace",
    )

    def log(kind, payload):
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "tt-log.py"), kind],
                       input=json.dumps(payload), encoding="utf-8", env=env, check=True)

    time.sleep(0.7)
    log("bash", {
        "session_id": "e2e-bash", "agent_type": "Explore", "tool_name": "Bash",
        "tool_input": {"command": f'rg -il "empty.state|empty_state" "{docs}" | sort'},
    })
    time.sleep(0.9)  # watcher must render the scan-only intermediate state
    log("read", {
        "session_id": "e2e-bash", "agent_type": "Explore", "tool_name": "Read",
        "tool_input": {"file_path": str(target)},
    })
    out, _ = watcher.communicate(timeout=30)
    assert watcher.returncode == 0

    plain = re.sub(r"\x1b\[[0-9;]*m", "", out)
    frames = plain.split("--frame--")
    initial = next(frame for frame in frames if "0 reads · 0 scans" in frame)
    discovered = next(frame for frame in frames if "0 reads · 1 scans" in frame)
    consulted = next(frame for frame in frames if "1 reads · 1 scans" in frame)
    assert "🔍" not in initial
    assert "🔍 docs/ui [Explore]" in discovered
    assert "empty-states.md" in consulted
