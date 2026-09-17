"""Guard the installers.

They are the first thing a non-technical user touches, and their failure modes
are silent. Windows is the primary target for Marina, so the batch file gets
the strictest checks.

Run:  python scripts/check_installers.py
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
failures: list[str] = []
notes: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{' — ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


def note(msg: str) -> None:
    notes.append(msg)
    print(f"  NOTE  {msg}")


def check_bash(path: Path, required: list[str], label: str) -> None:
    raw = path.read_bytes()
    text = raw.decode("utf-8", "replace")
    check(f"{label} exists", path.exists())
    if not path.exists():
        return
    mode = path.stat().st_mode
    check(f"{label} is executable", bool(mode & stat.S_IXUSR),
          oct(mode & 0o777))
    check(f"{label} has no CRLF (breaks bash)", b"\r\n" not in raw)
    check(f"{label} starts with a shebang", text.startswith("#!"))
    for token in required:
        check(f"{label} contains {token!r}", token in text)


def main() -> int:
    print("install.sh")
    check_bash(ROOT / "install.sh", [
        "set -uo pipefail",
        "astral.sh/uv/install.sh",     # self-bootstrapping, no prerequisites
        "uv tool install",
        "mm init",
        "mm connect-claude",
        "mm doctor",
    ], "install.sh")

    print("\nInstall Marina Memory.command")
    check_bash(ROOT / "Install Marina Memory.command", [
        "install.sh",
        "read -n 1",                  # keeps the window open so she can read it
    ], ".command")

    print("\nInstall Marina Memory.bat")
    bat_path = ROOT / "Install Marina Memory.bat"
    check("batch file exists", bat_path.exists())
    if bat_path.exists():
        raw = bat_path.read_bytes()
        text = raw.decode("utf-8", "replace")
        # THE Windows trap: cmd.exe mis-parses LF-only batch files, especially
        # around labels and goto. This was a real defect before 2026-09-17.
        check("batch file uses CRLF line endings", b"\r\n" in raw)
        bare_lf = raw.replace(b"\r\n", b"").count(b"\n")
        check("batch file has no bare LF", bare_lf == 0, f"{bare_lf} bare LF")
        for token in [
            "astral.sh/uv/install.ps1",  # bootstraps uv on a bare Windows box
            "UV_TOOL_BIN_DIR",
            "uv tool install",
            "mm init",
            "mm connect-claude",
            "mm doctor",
            "pause",                     # window must not vanish
            ":failed",
        ]:
            check(f".bat contains {token!r}", token in text)
        check(".bat quotes its own directory", 'cd /d "%~dp0"' in text)
        # A work/school PC may block the PowerShell bootstrap; the user needs
        # a copy-pasteable fallback rather than a dead end.
        check(".bat gives a manual fallback", "irm https://astral.sh/uv/install.ps1" in text)

    print("\nPlatform wording")
    sys.path.insert(0, str(ROOT))
    from memory_kit import config  # noqa: E402

    real = config.quit_claude_hint()
    check("quit hint is platform-aware", isinstance(real, str) and "quit" in real.lower(), real[:60])
    if os.environ.get("MM_CHECK_PLATFORM"):
        note("platform override set, skipping host-platform assertion")
    else:
        note(f"current platform hint: {real}")

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: {len(failures)} failed -> {failures}")
        return 1
    print("RESULT: all installer checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
