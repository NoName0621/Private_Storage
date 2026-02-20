import os
import sys
import subprocess
import platform
import venv
from pathlib import Path


def get_venv_python(base_dir: Path) -> Path:
    if platform.system() == "Windows":
        return base_dir / ".venv" / "Scripts" / "python.exe"
    return base_dir / ".venv" / "bin" / "python"


def ensure_venv_python(base_dir: Path) -> Path:
    venv_python = get_venv_python(base_dir)
    if not venv_python.exists():
        print("Creating virtual environment (.venv)...")
        venv.EnvBuilder(with_pip=True).create(str(base_dir / ".venv"))
    return venv_python


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    venv_python = ensure_venv_python(base_dir)
    current_python = Path(sys.executable).resolve()

    # If already running inside .venv, run start_server directly.
    if current_python == venv_python.resolve():
        from start_server import ServerManager
        manager = ServerManager()
        manager.run()
        return 0

    cmd = [str(venv_python), str(base_dir / "start_server.py")]
    result = subprocess.run(cmd, cwd=str(base_dir))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
