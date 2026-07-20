"""Prove the repository installs as a Claude Code marketplace plugin."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FILES = (
    ".claude-plugin/plugin.json",
    "hooks/claude-hooks.json",
    "hooks/hooks.json",
    "SKILL.md",
    "skills/tt/SKILL.md",
    "scripts/tt-log.py",
    "scripts/tt-doctor.py",
)


def run(*args: str, config_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="trigger-tree-plugin-smoke-") as temp:
        config_dir = Path(temp) / "claude"
        config_dir.mkdir()

        run(
            "npx",
            "claude",
            "plugin",
            "marketplace",
            "add",
            str(ROOT),
            "--scope",
            "user",
            config_dir=config_dir,
        )
        run(
            "npx",
            "claude",
            "plugin",
            "install",
            "trigger-tree@trigger-tree",
            "--scope",
            "user",
            config_dir=config_dir,
        )
        result = run("npx", "claude", "plugin", "list", "--json", config_dir=config_dir)

        installed = json.loads(result.stdout)
        matches = [item for item in installed if item["id"] == "trigger-tree@trigger-tree"]
        if len(matches) != 1 or not matches[0]["enabled"]:
            raise SystemExit("trigger-tree was not installed and enabled exactly once")

        install_path = Path(matches[0]["installPath"]).resolve()
        if not install_path.is_relative_to(config_dir.resolve()):
            raise SystemExit("plugin escaped the isolated Claude config directory")

        missing = [name for name in REQUIRED_FILES if not (install_path / name).is_file()]
        if missing:
            raise SystemExit(f"installed plugin is incomplete: {', '.join(missing)}")

        manifest = json.loads((install_path / ".claude-plugin/plugin.json").read_text())
        if matches[0]["version"] != manifest["version"]:
            raise SystemExit("installed version does not match plugin manifest")

        hooks = (install_path / "hooks" / "hooks.json").read_text()
        if "${CLAUDE_PLUGIN_ROOT}/scripts/tt-codex-hook.py" not in hooks:
            raise SystemExit("shared hooks do not use the cross-client plugin root")

        print(f"Installed trigger-tree v{manifest['version']} in an isolated Claude config")


if __name__ == "__main__":
    main()
