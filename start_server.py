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
from pathlib import Path

class ServerManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent.absolute()
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
        
    def start_server(self):
        """Start the application server based on OS"""
        system = self.detect_os()
        
        # Initialize database first
        print("Initializing database...")
        try:
            from run import init_db
            init_db()
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
                sys.executable,
                '-m', 'waitress',
                f'--threads={threads}',
                '--listen=127.0.0.1:5000',
                'run:app'
            ]
            print(f"Starting Waitress server on http://127.0.0.1:5000 (threads: {threads})")
        else:
            # Use Gunicorn for Mac/Linux
            cmd = [
                'gunicorn',
                '-w', str(workers),
                '-b', '127.0.0.1:5000',
                'run:app'
            ]
            print(f"Starting Gunicorn server on http://127.0.0.1:5000 (workers: {workers})")
            
        try:
            self.server_process = subprocess.Popen(cmd, cwd=str(self.base_dir))
            print(f"✓ Server started (PID: {self.server_process.pid})")
            return True
        except Exception as e:
            print(f"✗ Failed to start server: {e}")
            return False
            
    def start_updater(self):
        """Start the update service"""
        try:
            cmd = [sys.executable, 'update_service.py']
            self.updater_process = subprocess.Popen(cmd, cwd=str(self.base_dir))
            print(f"✓ Update service started (PID: {self.updater_process.pid})")
            return True
        except Exception as e:
            print(f"✗ Failed to start update service: {e}")
            return False
            
    def stop_server(self):
        """Stop the application server"""
        if self.server_process:
            print("Stopping server...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
                print("✓ Server stopped")
            except subprocess.TimeoutExpired:
                print("⚠ Forcing server shutdown...")
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
                print("✓ Update service stopped")
            except subprocess.TimeoutExpired:
                print("⚠ Forcing update service shutdown...")
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
                    print("⚠ Server process stopped unexpectedly")
                    self.running = False
                    break
                    
                # Check if updater is still running
                if self.updater_process and self.updater_process.poll() is not None:
                    print("⚠ Update service stopped")
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
        
        # Start server
        if not self.start_server():
            print("✗ Failed to start server, exiting")
            return
            
        # Wait a moment for server to initialize
        time.sleep(2)
        
        # Check if server is actually running
        if self.server_process.poll() is not None:
            print("✗ Server failed to start. Please check:")
            print("  1. Is waitress installed? Run: pip install waitress")
            print("  2. Is port 5000 already in use?")
            print("  3. Check server_output.log for errors")
            return
            
        # Start updater
        if not self.start_updater():
            print("⚠ Update service failed to start, but server is running")
            
        # Display info
        print("=" * 60)
        print("✓ Server is running at http://127.0.0.1:5000")
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
    manager = ServerManager()
    manager.run()
