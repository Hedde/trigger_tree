import os
import pathlib
import shutil
import subprocess

from conftest import SCRIPTS


def dryrun(project, mode="", **extra_env):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), TT_OPEN_DRYRUN="1")
    env.update(extra_env)
    args = [shutil.which("bash") or "bash", os.path.join(SCRIPTS, "tt-open.sh")]
    if mode:
        args.append(mode)
    return subprocess.run(args, env=env, capture_output=True, text=True)


def test_launcher_binds_split_to_exact_repo_even_with_shell_characters(tmp_path):
    project = tmp_path / "team's project $(wrong)"
    project.mkdir()
    result = dryrun(project)
    assert result.returncode == 0, result.stderr

    # Ask the shell to execute only the launcher's `cd` prefix. Successful pwd
    # proves quoting cannot redirect the watcher to another repository.
    prefix = result.stdout.strip().split(" && CLAUDE_PROJECT_DIR=", 1)[0]
    pwd_cmd = "pwd -W" if os.name == "nt" else "pwd"
    bash = shutil.which("bash") or "bash"
    pwd = subprocess.run(
        [bash, "-lc", prefix + f" && {pwd_cmd}"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert pathlib.Path(pwd).resolve() == project.resolve()
    assert "CLAUDE_PROJECT_DIR=" in result.stdout and "tt-watch.py" in result.stdout


def test_launcher_modes_and_invalid_mode(tmp_path):
    assert "--demo --client" in dryrun(tmp_path, "demo").stdout
    assert "--replay --client" in dryrun(tmp_path, "replay").stdout
    invalid = dryrun(tmp_path, "stale")
    assert invalid.returncode == 1 and "usage:" in invalid.stderr


def test_launcher_passes_explicit_or_detected_client(tmp_path):
    assert dryrun(tmp_path, TT_CLIENT="codex").stdout.rstrip().endswith("--client codex")
    assert (
        dryrun(tmp_path, CLAUDE_PLUGIN_ROOT="/plugin").stdout.rstrip().endswith("--client claude")
    )
    assert dryrun(tmp_path, CODEX_HOME="/codex").stdout.rstrip().endswith("--client codex")


def test_installed_cache_path_is_a_client_detection_fallback(tmp_path):
    source = pathlib.Path(SCRIPTS) / "tt-open.sh"
    for cache_dir, expected in (
        (".claude/plugins/cache", "claude"),
        (".codex/plugins/cache", "codex"),
    ):
        scripts = tmp_path / cache_dir / "trigger-tree/1.6.4/scripts"
        scripts.mkdir(parents=True)
        manifest_dir = scripts.parent / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text('{"version": "1.6.4"}')
        launcher = scripts / "tt-open.sh"
        shutil.copy(source, launcher)
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("CLAUDE_PLUGIN_ROOT", "CODEX_HOME", "PLUGIN_ROOT", "TT_CLIENT")
        }
        env.update(CLAUDE_PROJECT_DIR=str(tmp_path), TT_OPEN_DRYRUN="1")
        result = subprocess.run(
            [shutil.which("bash") or "bash", launcher], env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.rstrip().endswith(f"--client {expected}")
