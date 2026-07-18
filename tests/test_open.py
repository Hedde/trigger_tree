import os
import pathlib
import shutil
import subprocess

from conftest import SCRIPTS


def dryrun(project, mode=""):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), TT_OPEN_DRYRUN="1")
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
    assert dryrun(tmp_path, "demo").stdout.rstrip().endswith("--demo")
    assert dryrun(tmp_path, "replay").stdout.rstrip().endswith("--replay")
    invalid = dryrun(tmp_path, "stale")
    assert invalid.returncode == 1 and "usage:" in invalid.stderr
