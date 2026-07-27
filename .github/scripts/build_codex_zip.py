#!/usr/bin/env python3
"""Build the deterministic Codex plugin upload archive."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "dist-submissions" / "trigger-tree-codex.zip"
TIMESTAMP = (1980, 1, 1, 0, 0, 0)

# Keep this explicit: a missing runtime dependency must fail the release build
# instead of producing a plausible-looking, incomplete upload.
FILES = {
    "LICENSE": "LICENSE",
    "CHANGELOG.md": "CHANGELOG.md",
    "PRIVACY.md": "PRIVACY.md",
    "README.md": "README.md",
    "hooks/hooks.json": "hooks/hooks.json",
    "scripts/tt-stats.py": "scripts/tt-stats.py",
    "scripts/tt-suggestions.py": "scripts/tt-suggestions.py",
    "scripts/tt-shell-capture.sh": "scripts/tt-shell-capture.sh",
    "scripts/tt-codex-hook.py": "scripts/tt-codex-hook.py",
    "scripts/tt-config.sh": "scripts/tt-config.sh",
    "scripts/tt-setup.py": "scripts/tt-setup.py",
    "scripts/tt-tips.py": "scripts/tt-tips.py",
    "scripts/tt-publish-badge.sh": "scripts/tt-publish-badge.sh",
    "scripts/tt-doctor.py": "scripts/tt-doctor.py",
    "scripts/tt-watch.py": "scripts/tt-watch.py",
    "scripts/tt-report.py": "scripts/tt-report.py",
    "scripts/tt-gate.py": "scripts/tt-gate.py",
    "scripts/tt-instructions.py": "scripts/tt-instructions.py",
    "scripts/tt_adherence.py": "scripts/tt_adherence.py",
    "scripts/validate_palette.js": "scripts/validate_palette.js",
    "scripts/tt-statusline.py": "scripts/tt-statusline.py",
    "scripts/tt_scope.py": "scripts/tt_scope.py",
    "scripts/tt-uninstall.py": "scripts/tt-uninstall.py",
    "scripts/tt_runtime.py": "scripts/tt_runtime.py",
    "scripts/tt-open.sh": "scripts/tt-open.sh",
    "scripts/tt-log.py": "scripts/tt-log.py",
    "codex-skills/trigger-tree/SKILL.md": "skills/trigger-tree/SKILL.md",
    "assets/trigger-tree-logo.png": "assets/trigger-tree-logo.png",
    ".codex-plugin/plugin.json": ".codex-plugin/plugin.json",
}


def _info(name: str, mode: int) -> ZipInfo:
    info = ZipInfo(name, TIMESTAMP)
    info.create_system = 3
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def build(output: Path = DEFAULT_OUTPUT) -> Path:
    """Write *output* atomically with stable order, metadata, and compression."""
    output = output.resolve()
    missing = [source for source in FILES if not (ROOT / source).is_file()]
    if missing:
        raise FileNotFoundError(f"missing Codex package inputs: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            directories = {
                parent
                for destination in FILES.values()
                for parent in Path(destination).parents
                if str(parent) != "."
            }
            entries = [(f"{directory.as_posix()}/", None) for directory in directories]
            entries.extend((destination, source) for source, destination in FILES.items())
            for destination, source in sorted(entries):
                if source is None:
                    archive.writestr(_info(destination, 0o40755), b"")
                else:
                    source_path = ROOT / source
                    mode = 0o100755 if os.access(source_path, os.X_OK) else 0o100644
                    archive.writestr(_info(destination, mode), source_path.read_bytes())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"archive path (default: {DEFAULT_OUTPUT.relative_to(ROOT)})",
    )
    args = parser.parse_args(argv)
    output = build(args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
