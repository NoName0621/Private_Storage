"""
Simplified Server Startup Script with Auto-Update Service
Manages both the application server and update service
"""

import os
import sys
import time
import signal
import platform
import subprocess
import threading
import venv
from pathlib import Path

def get_venv_python(base_dir: Path) -> Path:
    if platform.system() == "Windows":
        return base_dir / ".venv" / "Scripts" / "python.exe"
    return base_dir / ".venv" / "bin" / "python"


def build_venv_env(base_dir: Path, base_env=None):
    env = dict(base_env or os.environ)
    venv_dir = base_dir / ".venv"
    if platform.system() == "Windows":
        venv_bin = venv_dir / "Scripts"
    else:
        venv_bin = venv_dir / "bin"
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
    return env


def bootstrap_and_reexec_if_needed():
    base_dir = Path(__file__).resolve().parent
    venv_python = get_venv_python(base_dir)
    if not venv_python.exists():
        print("Creating virtual environment (.venv)...")
        venv.EnvBuilder(with_pip=True).create(str(base_dir / ".venv"))

    current_python = Path(sys.executable).resolve()
    target_python = venv_python.resolve()
    if current_python != target_python:
        print("Re-launching with virtual environment Python...")
        env = build_venv_env(base_dir)
        cmd = [str(venv_python), str(base_dir / "start_server.py")]
        result = subprocess.run(cmd, cwd=str(base_dir), env=env)
        raise SystemExit(result.returncode)


class ServerManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent.absolute()
        self.venv_dir = self.base_dir / '.venv'
        self.python_executable = Path(sys.executable)
        self.server_process = None
        self.updater_process = None
        self.restart_flag = self.base_dir / '.restart_required'
        self.running = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\nShutdown signal received")
        self.running = False
        self.stop_all()
        sys.exit(0)
        
    def detect_os(self):
        """Detect operating system"""
        return platform.system()

    def get_venv_python(self):
        """Get venv Python executable path"""
        if self.detect_os() == 'Windows':
            return self.venv_dir / 'Scripts' / 'python.exe'
        return self.venv_dir / 'bin' / 'python'

    def get_venv_env(self):
        """Build environment variables equivalent to venv activation."""
        return build_venv_env(self.base_dir)

    def ensure_pip_available(self):
        """Ensure pip is available in the selected Python environment"""
        pip_check_cmd = [str(self.python_executable), '-m', 'pip', '--version']
        try:
            subprocess.run(
                pip_check_cmd,
                cwd=str(self.base_dir),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            pass

        print("pip is missing in the virtual environment. Bootstrapping with ensurepip...")
        ensurepip_cmd = [str(self.python_executable), '-m', 'ensurepip', '--upgrade']
        try:
            subprocess.run(ensurepip_cmd, cwd=str(self.base_dir), check=True, env=self.get_venv_env())
        except Exception as e:
            print(f"Failed to bootstrap pip with ensurepip: {e}")
            return False

        # Validate pip after bootstrapping
        try:
            subprocess.run(
                pip_check_cmd,
                cwd=str(self.base_dir),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("pip bootstrapped successfully")
            return True
        except Exception as e:
            print(f"pip is still unavailable after ensurepip: {e}")
            return False

    def ensure_venv_and_requirements(self):
        """Create virtual environment and install dependencies if needed"""
        requirements_path = self.base_dir / 'requirements.txt'
        venv_python = self.get_venv_python()

        if not venv_python.exists():
            print("Creating virtual environment (.venv)...")
            try:
                venv.EnvBuilder(with_pip=True).create(str(self.venv_dir))
                print("[OK] Virtual environment created")
            except Exception as e:
                print(f"[ERROR] Failed to create virtual environment: {e}")
                return False

        self.python_executable = venv_python

        if not self.ensure_pip_available():
            return False

        if not requirements_path.exists():
            print("requirements.txt not found, skipping dependency installation")
            return True

        print("Installing dependencies from requirements.txt...")
        install_cmd = [
            str(self.python_executable),
            '-m',
            'pip',
            'install',
            '--disable-pip-version-check',
            '-r',
            str(requirements_path)
        ]
        try:
            subprocess.run(install_cmd, cwd=str(self.base_dir), check=True, env=self.get_venv_env())
            print("[OK] Dependencies installed")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to install dependencies: {e}")
            return False
        
    def start_server(self):
        """Start the application server based on OS"""
        system = self.detect_os()
        
        # Initialize database first
        print("Initializing database...")
        try:
            init_cmd = [str(self.python_executable), '-c', 'from run import init_db; init_db()']
            subprocess.run(init_cmd, cwd=str(self.base_dir), check=True, env=self.get_venv_env())
        except Exception as e:
            print(f"Database initialization: {e}")
        
        # Load config for server settings
        try:
            from config import Config
            workers = Config.SERVER_WORKERS
            threads = Config.SERVER_THREADS
        except Exception as e:
            print(f"Warning: Could not load config, using defaults: {e}")
            workers = 4
            threads = 4
        
        if system == 'Windows':
            # Use Waitress for Windows
            cmd = [
                str(self.python_executable),
                '-m', 'waitress',
                f'--threads={threads}',
                '--listen=127.0.0.1:5000',
                'run:app'
            ]
            print(f"Starting Waitress server on http://127.0.0.1:5000 (threads: {threads})")
        else:
            # Use Gunicorn for Mac/Linux
            cmd = [
                str(self.python_executable),
                '-m',
                'gunicorn',
                '-w', str(workers),
                '-b', '127.0.0.1:5000',
                'run:app'
            ]
            print(f"Starting Gunicorn server on http://127.0.0.1:5000 (workers: {workers})")
            
        try:
            self.server_process = subprocess.Popen(cmd, cwd=str(self.base_dir), env=self.get_venv_env())
            print(f"[OK] Server started (PID: {self.server_process.pid})")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start server: {e}")
            return False
            
    def start_updater(self):
        """Start the update service"""
        try:
            cmd = [str(self.python_executable), 'update_service.py']
            self.updater_process = subprocess.Popen(cmd, cwd=str(self.base_dir), env=self.get_venv_env())
            print(f"[OK] Update service started (PID: {self.updater_process.pid})")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start update service: {e}")
            return False
            
    def stop_server(self):
        """Stop the application server"""
        if self.server_process:
            print("Stopping server...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
                print("[OK] Server stopped")
            except subprocess.TimeoutExpired:
                print("[WARN] Forcing server shutdown...")
                self.server_process.kill()
            except Exception as e:
                print(f"Error stopping server: {e}")
            finally:
                self.server_process = None
                
    def stop_updater(self):
        """Stop the update service"""
        if self.updater_process:
            print("Stopping update service...")
            try:
                self.updater_process.terminate()
                self.updater_process.wait(timeout=5)
                print("[OK] Update service stopped")
            except subprocess.TimeoutExpired:
                print("[WARN] Forcing update service shutdown...")
                self.updater_process.kill()
            except Exception as e:
                print(f"Error stopping update service: {e}")
            finally:
                self.updater_process = None
                
    def stop_all(self):
        """Stop all processes"""
        self.stop_server()
        self.stop_updater()
        
    def restart_server_only(self):
        """Restart only the server process"""
        print("\n" + "=" * 60)
        print("RESTARTING SERVER FOR UPDATE")
        print("=" * 60)
        
        self.stop_server()
        time.sleep(2)  # Wait for port to be released
        self.start_server()
        
        # Remove restart flag
        if self.restart_flag.exists():
            self.restart_flag.unlink()
            
    def monitor_processes(self):
        """Monitor processes and handle restarts"""
        while self.running:
            try:
                # Check for restart flag (set by updater)
                if self.restart_flag.exists():
                    self.restart_server_only()
                    
                # Check if server is still running
                if self.server_process and self.server_process.poll() is not None:
                    print("[WARN] Server process stopped unexpectedly")
                    self.running = False
                    break
                    
                # Check if updater is still running
                if self.updater_process and self.updater_process.poll() is not None:
                    print("[WARN] Update service stopped")
                    # Updater might stop naturally, don't restart
                    
                time.sleep(5)  # Check every 5 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(10)
                
    def run(self):
        """Main execution"""
        print("=" * 60)
        print("Private Storage Server Manager")
        print("=" * 60)

        if not self.ensure_venv_and_requirements():
            print("Environment setup failed, exiting")
            return
        
        # Start server
        if not self.start_server():
            print("[ERROR] Failed to start server, exiting")
            return
            
        # Wait a moment for server to initialize
        time.sleep(2)
        
        # Check if server is actually running
        if self.server_process.poll() is not None:
            print("[ERROR] Server failed to start. Please check:")
            print("  1. Is waitress installed? Run: pip install waitress")
            print("  2. Is port 5000 already in use?")
            print("  3. Check server_output.log for errors")
            return
            
        # Start updater
        if not self.start_updater():
            print("[WARN] Update service failed to start, but server is running")
            
        # Display info
        print("=" * 60)
        print("[OK] Server is running at http://127.0.0.1:5000")
        print("  Press Ctrl+C to stop")
        print("=" * 60)
        print()
        
        # Monitor processes
        try:
            self.monitor_processes()
        except KeyboardInterrupt:
            print("\nShutdown requested...")
        finally:
            self.stop_all()
            print("Server manager stopped")

if __name__ == '__main__':
    bootstrap_and_reexec_if_needed()
    manager = ServerManager()
    manager.run()


