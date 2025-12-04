"""
Auto-Update Service for Private Storage
Periodically checks GitHub releases and updates the application automatically
"""

import os
import sys
import time
import json
import zipfile
import shutil
import logging
import requests
import psutil
import signal
from pathlib import Path
from datetime import datetime
from packaging import version

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UpdateService:
    def __init__(self, config_path='update_config.json'):
        """Initialize the update service"""
        self.config = self.load_config(config_path)
        self.current_version = self.get_current_version()
        self.base_dir = Path(__file__).parent.absolute()
        self.backup_dir = self.base_dir / 'backup'
        self.server_pid = None
        
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
            
    def get_current_version(self):
        """Read current version from version.txt"""
        try:
            with open('version.txt', 'r', encoding='utf-8') as f:
                ver = f.read().strip()
            logger.info(f"Current version: {ver}")
            return version.parse(ver)
        except Exception as e:
            logger.error(f"Failed to read version.txt: {e}")
            return version.parse("0.0.0")
            
    def get_latest_release(self):
        """Fetch latest release information from GitHub"""
        api_url = f"https://api.github.com/repos/{self.config['github_repo']}/releases/latest"
        
        try:
            logger.info(f"Checking for updates from {api_url}")
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            release_data = response.json()
            tag_name = release_data['tag_name'].lstrip('v')  # Remove 'v' prefix if present
            latest_ver = version.parse(tag_name)
            
            # Find the ZIP asset
            zip_asset = None
            for asset in release_data.get('assets', []):
                if asset['name'].endswith('.zip'):
                    zip_asset = asset
                    break
                    
            # If no asset found, use source code zip
            if not zip_asset:
                zip_asset = {
                    'browser_download_url': f"https://github.com/{self.config['github_repo']}/archive/refs/tags/{release_data['tag_name']}.zip",
                    'name': f"{release_data['tag_name']}.zip"
                }
            
            logger.info(f"Latest release: {tag_name}")
            return {
                'version': latest_ver,
                'tag_name': release_data['tag_name'],
                'download_url': zip_asset['browser_download_url'],
                'filename': zip_asset['name']
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch release info: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing release data: {e}")
            return None
            
    def download_file(self, url, filename):
        """Download file from URL"""
        try:
            logger.info(f"Downloading from {url}")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            file_path = self.base_dir / filename
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            logger.info(f"Downloaded to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
            
    def create_backup(self):
        """Create backup of current installation"""
        if not self.config.get('backup_enabled', True):
            return True
            
        try:
            # Create backup directory with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.backup_dir / f"backup_{self.current_version}_{timestamp}"
            backup_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating backup at {backup_path}")
            
            # Copy important files
            for item in self.base_dir.iterdir():
                if item.name in ['.venv', 'backup', '__pycache__', '.git']:
                    continue
                    
                dest = backup_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, ignore=shutil.ignore_patterns('*.pyc', '__pycache__'))
                else:
                    shutil.copy2(item, dest)
                    
            logger.info("Backup created successfully")
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None
            
    def extract_update(self, zip_path):
        """Extract update files"""
        try:
            logger.info(f"Extracting {zip_path}")
            temp_dir = self.base_dir / 'temp_update'
            
            # Clean temp directory if exists
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir()
            
            # Extract zip
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
            # Find the root directory (GitHub creates a subdirectory)
            extracted_items = list(temp_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                source_dir = extracted_items[0]
            else:
                source_dir = temp_dir
                
            logger.info(f"Extracted to {source_dir}")
            return source_dir
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None
            
    def apply_update(self, source_dir):
        """Apply update by copying files"""
        try:
            logger.info("Applying update...")
            protected = set(self.config.get('protected_files', []))
            
            for item in source_dir.iterdir():
                # Skip protected files
                if item.name in protected or any(item.name.startswith(p.rstrip('/')) for p in protected):
                    logger.info(f"Skipping protected: {item.name}")
                    continue
                    
                dest = self.base_dir / item.name
                
                # Remove existing file/directory
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                        
                # Copy new file/directory
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
                    
                logger.info(f"Updated: {item.name}")
                
            logger.info("Update applied successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            return False
            
    def update_version_file(self, new_version):
        """Update version.txt with new version"""
        try:
            with open('version.txt', 'w', encoding='utf-8') as f:
                f.write(str(new_version))
            logger.info(f"Version updated to {new_version}")
            return True
        except Exception as e:
            logger.error(f"Failed to update version file: {e}")
            return False
            
    def cleanup(self, zip_path=None):
        """Clean up temporary files"""
        try:
            if zip_path and zip_path.exists():
                zip_path.unlink()
                logger.info(f"Removed {zip_path}")
                
            temp_dir = self.base_dir / 'temp_update'
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.info("Removed temp directory")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            
    def restart_server(self):
        """Restart the application server"""
        logger.info("Restarting server...")
        
        # Signal the parent process (start_server.py) to restart
        # We'll use a flag file approach
        flag_file = self.base_dir / '.restart_required'
        flag_file.touch()
        
        logger.info("Restart signal sent")
        
    def check_and_update(self):
        """Main update check and execution logic"""
        logger.info("=" * 60)
        logger.info("Starting update check")
        logger.info("=" * 60)
        
        # Get latest release
        release_info = self.get_latest_release()
        if not release_info:
            logger.warning("Could not fetch release information")
            return False
            
        latest_ver = release_info['version']
        logger.info(f"Current: {self.current_version}, Latest: {latest_ver}")
        
        # Compare versions
        if latest_ver <= self.current_version:
            logger.info("No update available")
            return False
            
        logger.info(f"New version available: {latest_ver}")
        
        # Download update
        zip_path = self.download_file(
            release_info['download_url'],
            release_info['filename']
        )
        if not zip_path:
            return False
            
        try:
            # Create backup
            backup_path = self.create_backup()
            if not backup_path:
                logger.error("Backup failed, aborting update")
                self.cleanup(zip_path)
                return False
                
            # Extract update
            source_dir = self.extract_update(zip_path)
            if not source_dir:
                logger.error("Extraction failed, aborting update")
                self.cleanup(zip_path)
                return False
                
            # Apply update
            if not self.apply_update(source_dir):
                logger.error("Update application failed")
                self.cleanup(zip_path)
                return False
                
            # Update version file
            if not self.update_version_file(latest_ver):
                logger.warning("Version file update failed")
                
            # Cleanup
            self.cleanup(zip_path)
            
            # Restart server
            self.restart_server()
            
            logger.info("=" * 60)
            logger.info(f"Update completed successfully: {self.current_version} -> {latest_ver}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Update process failed: {e}")
            self.cleanup(zip_path)
            return False
            
    def run(self):
        """Main service loop"""
        logger.info("Update Service started")
        logger.info(f"Repository: {self.config['github_repo']}")
        logger.info(f"Check interval: {self.config['check_interval_seconds']} seconds")
        
        # Initial check on startup
        self.check_and_update()
        
        # Periodic checks
        while True:
            try:
                time.sleep(self.config['check_interval_seconds'])
                self.check_and_update()
            except KeyboardInterrupt:
                logger.info("Update service stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

if __name__ == '__main__':
    try:
        service = UpdateService()
        service.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
