"""Smoke tests: every CLI command can be invoked with --help and prints a stub."""

from __future__ import annotations

from typer.testing import CliRunner

from ai_studio.cli import app

runner = CliRunner()


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AI Influencer Studio" in result.stdout


def test_init_runs() -> None:
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "stub" in result.stdout


def test_run_once_requires_args() -> None:
    result = runner.invoke(app, ["run-once"])
    assert result.exit_code != 0


def test_run_once_with_args() -> None:
    result = runner.invoke(app, ["run-once", "--persona", "golfer", "--activity", "golf_practice"])
    assert result.exit_code == 0
    assert "golfer" in result.stdout
    assert "golf_practice" in result.stdout
