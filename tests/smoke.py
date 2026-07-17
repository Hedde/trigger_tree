#!/usr/bin/env python3
"""Trigger Tree smoke test — exercises stats, report, logger and statusline
against the fixture project. Exits non-zero on any failed assertion."""
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
FIXTURE = os.path.join(REPO, "tests", "fixture-project")


def run(script, args=None, project=None, stdin=None, env_extra=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project or FIXTURE)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script)] + (args or []),
        input=stdin, capture_output=True, text=True, env=env, check=True,
    ).stdout


def test_stats():
    s = json.loads(run("tt-stats.py"))
    assert s["maturity"] == "cold-start", s["maturity"]
    assert s["totals"]["reads"] == 4
    assert s["totals"]["scans"] == 1
    assert s["totals"]["skill_uses"] == 1
    assert s["sessions"] == 2
    assert s["untouched"] == ["agents/x.md"], s["untouched"]
    assert s["always_loaded"] == ["CLAUDE.md"], s["always_loaded"]  # used skill excluded
    assert s["skills"][0]["name"] == "deploy" and s["skills"][0]["uses"] == 1
    assert len(s["trend"]) == 2 and s["trend"][0]["hunting_ratio"] == 0.5
    assert s["notes"][0]["text"] == "sharpened UX router"
    assert len(s["clusters"]) == 1, s["clusters"]  # Jaccard 2/3 merges both buckets
    assert s["clusters"][0]["count"] == 2 and s["clusters"][0]["variants"] == 2
    print("stats OK")


def test_report():
    out_path = run("tt-report.py").strip()
    html = open(out_path).read()
    assert "<title>Trigger Tree Report</title>" in html
    assert "Task clusters" in html and "Skill usage" in html and "sharpened UX router" in html
    print("report OK")


def test_logger_and_statusline():
    with tempfile.TemporaryDirectory() as tmp:
        read_event = json.dumps({
            "session_id": "S", "tool_name": "Read",
            "tool_input": {"file_path": os.path.join(tmp, "docs", "x.md")},
        })
        run("tt-log.py", ["read"], project=tmp, stdin=read_event)
        hist = os.path.join(tmp, ".trigger-tree", "history.jsonl")
        line = json.loads(open(hist).read().splitlines()[0])
        assert line["t"] == "read" and line["path"] == "docs/x.md"

        run("tt-log.py", ["skill"], project=tmp, stdin=json.dumps(
            {"session_id": "S", "tool_name": "Skill", "tool_input": {"skill": "deploy"}}))
        assert '"skill": "deploy"' in open(hist).read() or '"skill":"deploy"' in open(hist).read()

        run("tt-log.py", ["note", "router", "tweak"], project=tmp,
            env_extra={"CLAUDE_SESSION_ID": "S"})
        assert "router tweak" in open(hist).read()

        out = run("tt-statusline.py", project=tmp, stdin=json.dumps({"session_id": "S"}))
        assert "1 files" in out, out
        print("logger + statusline OK")

    with tempfile.TemporaryDirectory() as tmp:
        # prompt privacy: hash mode stores a digest, not the text
        os.makedirs(os.path.join(tmp, ".trigger-tree"))
        with open(os.path.join(tmp, ".trigger-tree", "config.sh"), "w") as fh:
            fh.write("TT_LOG_PROMPTS='hash'\nTT_ROTATE_BYTES='10'\n")
        run("tt-log.py", ["prompt"], project=tmp,
            stdin=json.dumps({"session_id": "S", "prompt": "secret plans"}))
        content = open(os.path.join(tmp, ".trigger-tree", "history.jsonl")).read()
        assert "prompt_hash" in content and "secret plans" not in content

        # rotation: tiny TT_ROTATE_BYTES forces an archive on the next append
        run("tt-log.py", ["prompt"], project=tmp,
            stdin=json.dumps({"session_id": "S", "prompt": "another prompt"}))
        files = os.listdir(os.path.join(tmp, ".trigger-tree"))
        archives = [f for f in files if f.startswith("history-")]
        assert archives, files
        print("privacy + rotation OK")


def test_setup():
    with tempfile.TemporaryDirectory() as tmp:
        out = run("tt-setup.py", ["--with-config"], project=tmp)
        assert os.path.isfile(os.path.join(tmp, ".claude", "tt-statusline.py"))
        assert os.path.isfile(os.path.join(tmp, ".trigger-tree", "config.sh"))
        settings = json.load(open(os.path.join(tmp, ".claude", "settings.json")))
        assert settings["statusLine"]["command"].endswith("tt-statusline.py")
        gitignore = open(os.path.join(tmp, ".gitignore")).read()
        assert ".trigger-tree/*" in gitignore and "!.trigger-tree/config.sh" in gitignore
        # idempotent: second run must not duplicate or overwrite
        out2 = run("tt-setup.py", project=tmp)
        assert "skipped" in out2
        assert open(os.path.join(tmp, ".gitignore")).read() == gitignore
        print("setup OK")


if __name__ == "__main__":
    test_stats()
    test_report()
    test_logger_and_statusline()
    test_setup()
    print("all smoke tests passed")
