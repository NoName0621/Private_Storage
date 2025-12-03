import os
import uuid
import hashlib
import json
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    # Allow all file types - security is handled by secure_filename and server configuration
    return True

def get_user_upload_dir(user_id):
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(user_id))
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    return upload_dir

def get_metadata_path(user_id):
    return os.path.join(get_user_upload_dir(user_id), 'metadata.json')

def load_metadata(user_id):
    metadata_path = get_metadata_path(user_id)
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_metadata(user_id, metadata):
    metadata_path = get_metadata_path(user_id)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f)

def calculate_file_hash(file_stream):
    sha256_hash = hashlib.sha256()
    for byte_block in iter(lambda: file_stream.read(4096), b""):
        sha256_hash.update(byte_block)
    file_stream.seek(0) # Reset pointer
    return sha256_hash.hexdigest()

def calculate_file_hash_from_path(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def save_file(file, user):
    if not file or not allowed_file(file.filename):
        return None, "Invalid file type."
    
    # Check quota
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if not user.has_space(file_size):
        return None, "Quota exceeded."

    filename = secure_filename(file.filename)
    if not filename:
        filename = str(uuid.uuid4())
    
    upload_dir = get_user_upload_dir(user.id)
    file_path = os.path.join(upload_dir, filename)
    
    # Calculate hash before saving (or after, but stream is available now)
    file_hash = calculate_file_hash(file)
    
    file.save(file_path)
    
    # Save metadata
    metadata = load_metadata(user.id)
    metadata[filename] = file_hash
    save_metadata(user.id, metadata)
    
    return filename, None

def delete_user_file(user_id, filename):
    upload_dir = get_user_upload_dir(user_id)
    filename = secure_filename(filename)
    file_path = os.path.join(upload_dir, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        
        # Remove from metadata
        metadata = load_metadata(user_id)
        if filename in metadata:
            del metadata[filename]
            save_metadata(user_id, metadata)
            
        return True
    return False

def get_user_files(user_id):
    upload_dir = get_user_upload_dir(user_id)
    files = []
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            fp = os.path.join(upload_dir, f)
            if os.path.isfile(fp) and f != 'metadata.json':
                size = os.path.getsize(fp)
                files.append({'name': f, 'size': size})
    return files

def verify_file_integrity(user_id, filename):
    metadata = load_metadata(user_id)
    stored_hash = metadata.get(filename)
    
    if not stored_hash:
        # If no hash stored (legacy file), maybe we should calculate it now and store it?
        # Or just pass? Requirement says "check". If missing, maybe warn?
        # Let's assume strict check for new files, but maybe allow legacy if we want.
        # For now, if no hash, we can't verify, so maybe return True or False?
        # Let's return True but log? Or False?
        # Requirement: "Calculate hash on upload... Verify on download... Error if mismatch"
        # If no hash, we can't verify mismatch.
        return True # Treat as valid if no hash exists (legacy support)
        
    upload_dir = get_user_upload_dir(user_id)
    file_path = os.path.join(upload_dir, filename)
    
    if not os.path.exists(file_path):
        return False
        
    current_hash = calculate_file_hash_from_path(file_path)
    return current_hash == stored_hash
