import json
import os

import pytest
from conftest import load_script


def test_full_setup_and_idempotency(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    out = capsys.readouterr().out
    assert "updated" in out and "copied" in out and "created" in out
    assert "watched: 0 of 0 markdown files" in out
    assert os.path.isfile(tmp_path / ".claude" / "tt-statusline.py")
    assert os.path.isfile(tmp_path / ".trigger-tree" / "config.sh")
    assert "TT_LOG_PROMPTS='truncate'" in (tmp_path / ".trigger-tree" / "config.sh").read_text()
    settings = json.load(open(tmp_path / ".claude" / "settings.json"))
    assert settings["statusLine"]["command"].endswith("tt-statusline.py")
    gitignore = (tmp_path / ".gitignore").read_text()
    assert ".trigger-tree/*" in gitignore and "!.trigger-tree/config.sh" in gitignore

    mod.main([])  # second run: everything skipped, nothing duplicated
    out2 = capsys.readouterr().out
    assert out2.count("skipped") >= 3
    assert (tmp_path / ".gitignore").read_text() == gitignore


def test_safe_destination_rejects_mocked_symlink_on_every_platform(tmp_path, monkeypatch):
    mod = load_script("tt-setup.py", tmp_path)
    monkeypatch.setattr(mod.os.path, "lexists", lambda _path: True)
    monkeypatch.setattr(
        mod.os,
        "lstat",
        lambda _path: type("Stat", (), {"st_mode": mod.stat.S_IFLNK})(),
    )
    with pytest.raises(RuntimeError, match="symlink"):
        mod.assert_safe_destination(tmp_path / "target")


def test_setup_explicit_prompt_modes_update_only_prompt_setting(tmp_path, capsys):
    mod = load_script("tt-setup.py", tmp_path)
    mod.main(["--prompt-mode", "hash"])
    config = tmp_path / ".trigger-tree" / "config.sh"
    assert "TT_LOG_PROMPTS='hash'" in config.read_text()
    assert "hashes only" in capsys.readouterr().out

    mod.main(["--prompt-mode", "off"])
    assert "TT_LOG_PROMPTS='off'" in config.read_text()
    assert "markers only" in capsys.readouterr().out

    mod.main(["--prompt-mode", "truncate"])
    assert "TT_LOG_PROMPTS='truncate'" in config.read_text()
    assert "first 200 characters" in capsys.readouterr().out


def test_existing_config_is_preserved_without_explicit_mode(tmp_path, capsys):
    config_dir = tmp_path / ".trigger-tree"
    config_dir.mkdir()
    config = config_dir / "config.sh"
    config.write_text("TT_LOG_PROMPTS='hash'\nTT_ROTATE_BYTES='42'\n")
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    assert "existing prompt setting preserved" in capsys.readouterr().out
    assert config.read_text() == "TT_LOG_PROMPTS='hash'\nTT_ROTATE_BYTES='42'\n"


def test_prompt_assignment_is_appended_when_missing(tmp_path):
    config = tmp_path / "config.sh"
    config.write_text("TT_ROTATE_BYTES='42'\n")
    mod = load_script("tt-setup.py", tmp_path)
    assert mod.write_prompt_mode(config, "off") is True
    assert config.read_text().endswith("TT_LOG_PROMPTS='off'\n")
    assert mod.write_prompt_mode(config, "off") is False


def test_existing_statusline_left_untouched(tmp_path, monkeypatch, capsys):
    (tmp_path / ".claude").mkdir()
    original = {"statusLine": {"type": "command", "command": "my-own-line.sh"}}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(original))
    mod = load_script("tt-setup.py", tmp_path)
    mod.register_statusline()
    assert "left untouched" in capsys.readouterr().out
    assert json.load(open(tmp_path / ".claude" / "settings.json")) == original


def test_unparseable_settings_skipped(tmp_path, capsys):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{broken")
    mod = load_script("tt-setup.py", tmp_path)
    mod.register_statusline()
    assert "unparseable" in capsys.readouterr().out
    assert (tmp_path / ".claude" / "settings.json").read_text() == "{broken"


def test_gitignore_appends_to_existing(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text("node_modules\n")
    mod = load_script("tt-setup.py", tmp_path)
    mod.ensure_gitignore()
    content = (tmp_path / ".gitignore").read_text()
    assert content.startswith("node_modules\n") and ".trigger-tree/*" in content


def test_gitignore_without_trailing_newline(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text("node_modules")  # no trailing newline
    mod = load_script("tt-setup.py", tmp_path)
    mod.ensure_gitignore()
    content = (tmp_path / ".gitignore").read_text()
    assert "node_modules\n.trigger-tree/*" in content


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs elevated rights on Windows")
@pytest.mark.parametrize(
    "relative",
    (".gitignore", ".claude/tt-statusline.py", ".claude/settings.json", ".trigger-tree/config.sh"),
)
def test_setup_refuses_symlink_write_destinations(tmp_path, relative):
    victim = tmp_path / "outside"
    victim.write_text("untouched\n")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(victim)
    mod = load_script("tt-setup.py", tmp_path)
    with pytest.raises(RuntimeError, match="refusing symlink"):
        mod.main(["--prompt-mode", "off"])
    assert victim.read_text() == "untouched\n"


@pytest.mark.skipif(os.name == "nt", reason="Windows does not implement POSIX permission bits")
def test_setup_permissions_and_security_disclosure_are_consistent(tmp_path):
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    assert ((tmp_path / ".trigger-tree").stat().st_mode & 0o777) == 0o700
    repo = os.path.dirname(os.path.dirname(__file__))
    security = open(os.path.join(repo, "SECURITY.md"), encoding="utf-8").read()
    assert "recommended `/tt setup` flow stores" in security
    assert "200-character local preview by default" in security


def test_safe_destination_rejects_escape_non_directory_parent_and_directory_target(tmp_path):
    mod = load_script("tt-setup.py", tmp_path)
    with pytest.raises(RuntimeError, match="outside project"):
        mod.assert_safe_destination(tmp_path.parent / "outside")
    parent = tmp_path / "parent"
    parent.write_text("file")
    with pytest.raises(RuntimeError, match="non-directory parent"):
        mod.assert_safe_destination(parent / "child")
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(RuntimeError, match="non-regular destination"):
        mod.assert_safe_destination(directory)


def test_watch_scope_scanner_handles_layouts_skips_and_cap(tmp_path):
    mod = load_script("tt-setup.py", tmp_path)
    assert mod.scan_markdown(tmp_path, r"^docs/", limit=5)["markdown"] == 0
    (tmp_path / "README.md").write_text("root")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide")
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "ignored.md").write_text("ignored")
    result = mod.scan_markdown(tmp_path, r"^docs/", limit=10)
    assert (result["markdown"], result["watched"], result["capped"]) == (2, 1, False)
    assert "README\\.md" in mod.suggested_regex(result["paths"])
    capped = mod.scan_markdown(tmp_path, r"^docs/", limit=1)
    assert capped["visited"] == 1 and capped["capped"] is True


def test_setup_proposes_then_explicitly_applies_observed_watch_scope(tmp_path, capsys):
    (tmp_path / "README.md").write_text("root")
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    output = capsys.readouterr().out
    assert "watched: 0 of 1 markdown files" in output
    assert "suggested TT_WATCH_REGEX" in output
    config = tmp_path / ".trigger-tree" / "config.sh"
    assert "README\\.md" not in config.read_text()

    mod.main(["--apply-watch-suggestion"])
    assert "README\\.md" in config.read_text()
    assert "applied suggested TT_WATCH_REGEX" in capsys.readouterr().out


def test_watch_scope_config_fallbacks_and_assignment_append(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-setup.py", tmp_path)
    config = tmp_path / "config.sh"
    config.write_text("TT_LOG_PROMPTS='hash'\n")
    mod.write_assignment(config, "TT_WATCH_REGEX", r"^README\.md$")
    assert "TT_WATCH_REGEX='^README\\.md$'" in config.read_text()

    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert mod.effective_watch_regex() == r"(?!)"
    monkeypatch.setattr(
        mod,
        "scan_markdown",
        lambda *_args: {"visited": 5000, "markdown": 1, "watched": 0, "paths": [], "capped": True},
    )
    mod.audit_watch_scope()
    assert "scan capped at 5000 files" in capsys.readouterr().out
