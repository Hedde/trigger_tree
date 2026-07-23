"""Standalone `tt` console entry point dispatching to the bundled scripts."""

import runpy
import sys
from pathlib import Path

SUBCOMMANDS = (
    "doctor",
    "gate",
    "log",
    "report",
    "setup",
    "stats",
    "suggestions",
    "tips",
    "uninstall",
    "watch",
)
USAGE = f"usage: tt <{'|'.join(SUBCOMMANDS)}> [options]\n"


def script_path(name, package_dir=None):
    """Prefer the wheel's bundled copy; fall back to the repository layout."""
    package_dir = Path(__file__).parent if package_dir is None else Path(package_dir)
    packaged = package_dir / "_scripts" / f"tt-{name}.py"
    if packaged.is_file():
        return packaged
    return package_dir.resolve().parent / "scripts" / f"tt-{name}.py"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in ("-h", "--help"):
        sys.stdout.write(USAGE)
        return 0
    if not argv or argv[0] not in SUBCOMMANDS:
        sys.stderr.write(USAGE)
        return 2
    path = script_path(argv[0])
    sys.argv = [str(path), *argv[1:]]
    # `python3 script.py` puts the script's directory on sys.path; run_path does not.
    directory = str(path.parent)
    sys.path.insert(0, directory)
    try:
        runpy.run_path(str(path), run_name="__main__")
    finally:
        if directory in sys.path:
            sys.path.remove(directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
