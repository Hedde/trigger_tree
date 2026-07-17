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
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
    )
    time.sleep(0.8)
    event = json.dumps({"session_id": "e2e", "tool_name": "Read",
                        "tool_input": {"file_path": str(tmp_path / "docs" / "a.md")}})
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "tt-log.py"), "read"],
                   input=event, text=True, env=env, check=True)
    out, _ = watcher.communicate(timeout=30)
    assert watcher.returncode == 0

    plain = re.sub(r"\x1b\[[0-9;]*m", "", out)
    frames = plain.split("--frame--")
    assert "0 reads" in frames[0]                      # started empty
    assert "1 reads" in frames[-2] and "a.md" in frames[-2]  # picked up the external append
