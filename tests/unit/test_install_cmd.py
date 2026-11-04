"""Execute the real CMD entry point against a recording Docker test double."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires Windows cmd.exe")


def run_installer(tmp_path: Path, option: str, failure: str = "") -> tuple[int, str, str]:
    workspace = tmp_path / "checkout with spaces"
    scripts = workspace / "scripts/setup"
    scripts.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/setup/install.cmd", scripts / "install.cmd")
    binaries = tmp_path / "fake tools"
    binaries.mkdir()
    log = tmp_path / "docker-calls.log"
    (binaries / "docker.cmd").write_text(
        "@echo off\n"
        'echo %*>>"%SENTINEL_TEST_LOG%"\n'
        'if "%~1"=="info" (echo linux& exit /b 0)\n'
        'if "%~1"=="compose" if "%~2"=="build" '
        'if "%SENTINEL_TEST_FAIL%"=="build" exit /b 37\n'
        "exit /b 0\n",
        encoding="ascii",
    )
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "call", str(scripts / "install.cmd"), option],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "SENTINEL_TEST_LOG": str(log),
            "SENTINEL_TEST_FAIL": failure,
        },
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.returncode, result.stdout + result.stderr, log.read_text() if log.exists() else ""


def test_cmd_demo_is_explicit_and_runs_smoke(tmp_path: Path) -> None:
    code, output, calls = run_installer(tmp_path, "--demo")
    assert code == 0, output
    assert "operations_env.py --development --demo" in calls
    assert "seed_operations_demo.py --api http://api:8000" in calls
    assert "smoke.py --api http://api:8000 --dashboard http://dashboard:3000" in calls
    assert calls.index("operations_env.py") < calls.index(" up --build")
    assert "checkout with spaces:/workspace" in calls


def test_cmd_check_does_not_build_or_write_settings(tmp_path: Path) -> None:
    code, output, calls = run_installer(tmp_path, "--check")
    assert code == 0, output
    assert "config --quiet" in calls
    assert "build api" not in calls and "operations_env.py" not in calls


def test_cmd_build_failure_stops_before_startup(tmp_path: Path) -> None:
    code, output, calls = run_installer(tmp_path, "", failure="build")
    assert code == 1, output
    assert "build api" in calls
    assert "operations_env.py" not in calls and " up --build" not in calls
    assert "volume deletion" in output


def test_cmd_real_default_does_not_seed(tmp_path: Path) -> None:
    code, output, calls = run_installer(tmp_path, "")
    assert code == 0, output
    assert "operations_env.py --development" in calls
    assert "seed_operations_demo.py" not in calls


def test_cmd_rejects_unknown_option_without_docker(tmp_path: Path) -> None:
    code, output, calls = run_installer(tmp_path, "--unknown")
    assert code == 2 and "Unsupported arguments" in output
    assert not calls
