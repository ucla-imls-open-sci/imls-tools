"""Tests for installing and maintaining wbcheck: `update`, `doctor`,
install.sh, and packaging (every package file must ship)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from checker import app as app_mod
from checker.app import app

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent


def test_no_package_file_is_gitignored():
    # Regression: an unanchored `report.*` in .gitignore matched checker/report.py,
    # and the build backend honors .gitignore, so installs had no checker.report.
    tracked = subprocess.run(["git", "ls-files", "checker"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    ignored = subprocess.run(["git", "check-ignore", "--no-index", *tracked], cwd=ROOT,
                             capture_output=True, text=True).stdout.split()
    assert ignored == []


def test_quarto_extension_ships_inside_the_package():
    from checker.report import _EXTENSION_SRC

    assert _EXTENSION_SRC.is_dir()
    assert ROOT / "checker" in _EXTENSION_SRC.parents


def test_install_script_is_valid_posix_sh():
    assert subprocess.run(["sh", "-n", str(ROOT / "install.sh")]).returncode == 0


# -- update ----------------------------------------------------------------------


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def installed_clone(tmp_path, monkeypatch):
    """An 'origin' repo and an installed clone of it, with pixi faked."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", "-b", "main", cwd=origin)
    _git("config", "user.email", "t@example.org", cwd=origin)
    _git("config", "user.name", "T", cwd=origin)
    (origin / "pixi.toml").write_text("[workspace]\n")
    _git("add", ".", cwd=origin)
    _git("commit", "-q", "-m", "one", cwd=origin)
    clone = tmp_path / "clone"
    _git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    monkeypatch.setattr(app_mod, "INSTALL_ROOT", clone)

    pixi_calls = []
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "pixi":
            pixi_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(app_mod.subprocess, "run", fake_run)
    return origin, clone, pixi_calls


def test_update_already_current(installed_clone):
    _, _, pixi_calls = installed_clone
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "Already up to date" in result.output
    assert pixi_calls == []


def test_update_pulls_and_reinstalls(installed_clone):
    origin, clone, pixi_calls = installed_clone
    (origin / "new.txt").write_text("x")
    _git("add", ".", cwd=origin)
    _git("commit", "-q", "-m", "two", cwd=origin)
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0, result.output
    assert (clone / "new.txt").exists()
    assert pixi_calls and pixi_calls[0][:2] == ["pixi", "install"]
    assert "Updated" in result.output


def test_update_refuses_local_changes(installed_clone):
    _, clone, _ = installed_clone
    (clone / "pixi.toml").write_text("[workspace]\n# edited\n")
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1
    assert "uncommitted changes" in result.output


def test_update_refuses_non_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "INSTALL_ROOT", tmp_path)
    assert runner.invoke(app, ["update"]).exit_code == 2


# -- doctor ----------------------------------------------------------------------


def test_doctor_marks_missing_optional_tools(monkeypatch):
    import shutil
    import urllib.request

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)

    def no_server(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", no_server)
    rows = {name: ok for name, ok, _ in app_mod._doctor_rows()}
    assert rows["wbcheck"] is True and rows["git"] is True
    assert rows["gh (issues)"] is None
    assert rows["quarto (--html/--pdf)"] is None
    assert rows["claude backend"] is None
    assert rows["ollama backend"] is None
    assert runner.invoke(app, ["doctor"]).exit_code == 0


def test_readme_lists_every_rule_code():
    from checker.rules import RULES

    readme = (ROOT / "README.md").read_text()
    missing = [code for code in RULES if f"`{code}`" not in readme]
    assert missing == [], f"add these to README's rule tables: {missing}"
