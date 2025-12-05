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
            # Delete old backups first (keep only the most recent one)
            if self.backup_dir.exists():
                existing_backups = sorted(
                    [d for d in self.backup_dir.iterdir() if d.is_dir()],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                # Remove all existing backups (we'll create a new one)
                for old_backup in existing_backups:
                    try:
                        shutil.rmtree(old_backup)
                        logger.info(f"Removed old backup: {old_backup.name}")
                    except Exception as e:
                        logger.warning(f"Could not remove old backup {old_backup.name}: {e}")
            
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
            
    def merge_json_config(self, source_file, dest_file):
        """Merge JSON configuration files, preserving existing values"""
        try:
            # Read existing config
            with open(dest_file, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
            
            # Read new config
            with open(source_file, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
            
            # Track changes
            added_keys = []
            
            # Add new keys from new config
            for key, value in new_config.items():
                if key not in existing_config:
                    existing_config[key] = value
                    added_keys.append(key)
            
            # Write merged config
            with open(dest_file, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=4, ensure_ascii=False)
            
            if added_keys:
                logger.info(f"Merged {dest_file.name}: Added new keys: {', '.join(added_keys)}")
            else:
                logger.info(f"Merged {dest_file.name}: No new keys to add")
            
            # Also save the new version as .new for reference
            dest_new = dest_file.parent / f"{dest_file.name}.new"
            shutil.copy2(source_file, dest_new)
            logger.info(f"New version saved as: {dest_file.name}.new for reference")
            
            return True
        except Exception as e:
            logger.error(f"Failed to merge JSON config {dest_file.name}: {e}")
            return False
    
    def apply_update(self, source_dir):
        """Apply update by copying files"""
        try:
            logger.info("Applying update...")
            protected = set(self.config.get('protected_files', []))
            
            # First pass: Handle app directory specially - complete replacement
            app_dir_dest = self.base_dir / 'app'
            app_dir_source = source_dir / 'app'
            
            if app_dir_source.exists() and app_dir_source.is_dir():
                logger.info("Completely replacing app directory...")
                
                # Remove existing app directory
                if app_dir_dest.exists():
                    logger.info(f"Removing old app directory: {app_dir_dest}")
                    shutil.rmtree(app_dir_dest)
                
                # Copy new app directory
                logger.info(f"Copying new app directory from: {app_dir_source}")
                shutil.copytree(app_dir_source, app_dir_dest)
                logger.info("App directory replaced successfully")
            
            # Second pass: Update other files/directories
            for item in source_dir.iterdir():
                # Skip app directory (already handled above)
                if item.name == 'app':
                    continue
                
                # Handle protected files with smart merging
                if item.name in protected or any(item.name.startswith(p.rstrip('/')) for p in protected):
                    # Skip protected directories
                    if item.is_dir():
                        logger.info(f"Skipping protected directory: {item.name}")
                        continue
                    
                    dest = self.base_dir / item.name
                    
                    # JSON files: Smart merge
                    if item.suffix == '.json' and dest.exists():
                        logger.info(f"Smart merging protected JSON file: {item.name}")
                        if self.merge_json_config(item, dest):
                            continue
                        else:
                            # If merge fails, fall back to .new file
                            logger.warning(f"Merge failed, saving as .new instead")
                    
                    # Python files and others: Save as .new
                    dest_new = self.base_dir / f"{item.name}.new"
                    shutil.copy2(item, dest_new)
                    logger.info(f"Protected file saved as: {item.name}.new (please review and merge manually)")
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
            # Delete ZIP file
            if zip_path:
                if zip_path.exists():
                    zip_path.unlink()
                    logger.info(f"Removed update file: {zip_path}")
                else:
                    logger.warning(f"Update file not found: {zip_path}")
                
            # Delete temp directory
            temp_dir = self.base_dir / 'temp_update'
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.info("Removed temp directory")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            # Try to force delete the zip file if it exists
            if zip_path and zip_path.exists():
                try:
                    zip_path.unlink()
                    logger.info(f"Forced removal of update file: {zip_path}")
                except Exception as e2:
                    logger.error(f"Could not force remove update file: {e2}")
            
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
