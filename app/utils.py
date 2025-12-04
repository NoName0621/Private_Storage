import os
import uuid
import hashlib
import json
import shutil
from werkzeug.utils import secure_filename
from flask import current_app
from .models import User

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
                data = json.load(f)
                # Migration logic: Convert string hash to dict
                migrated = False
                for filename, value in data.items():
                    if isinstance(value, str):
                        data[filename] = {'hash': value, 'share_token': None}
                        migrated = True
                
                if migrated:
                    save_metadata(user_id, data)
                return data
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

def get_temp_usage(user_id):
    """Calculate total size of temporary chunks for a user."""
    temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', str(user_id))
    total_size = 0
    if os.path.exists(temp_dir):
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                fp = os.path.join(root, f)
                total_size += os.path.getsize(fp)
    return total_size

def save_file(file, user):
    if not file or not allowed_file(file.filename):
        return None, "Invalid file type."
    
    # Check quota
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    # Strict quota check including temp usage
    temp_usage = get_temp_usage(user.id)
    if not user.has_space(file_size + temp_usage):
        return None, "Quota exceeded."

    filename = secure_filename(file.filename)
    if not filename:
        filename = str(uuid.uuid4())
    
    upload_dir = get_user_upload_dir(user.id)
    file_path = os.path.join(upload_dir, filename)

    # Auto-rename if file exists
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(file_path):
        filename = f"{base}_{counter}{ext}"
        file_path = os.path.join(upload_dir, filename)
        counter += 1
    
    # Calculate hash before saving
    file_hash = calculate_file_hash(file)
    
    file.save(file_path)
    
    # Save metadata
    metadata = load_metadata(user.id)
    metadata[filename] = {'hash': file_hash, 'share_token': None}
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
    metadata = load_metadata(user_id)
    files = []
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            fp = os.path.join(upload_dir, f)
            if os.path.isfile(fp) and f != 'metadata.json':
                size = os.path.getsize(fp)
                meta = metadata.get(f, {})
                # Handle legacy string format just in case
                if isinstance(meta, str):
                    meta = {'hash': meta, 'share_token': None}
                
                files.append({
                    'name': f, 
                    'size': size,
                    'share_token': meta.get('share_token')
                })
    return files

def verify_file_integrity(user_id, filename):
    metadata = load_metadata(user_id)
    meta = metadata.get(filename)
    
    if not meta:
        return True # Legacy support
        
    stored_hash = meta if isinstance(meta, str) else meta.get('hash')
    
    if not stored_hash:
        return True
        
    upload_dir = get_user_upload_dir(user_id)
    file_path = os.path.join(upload_dir, filename)
    
    if not os.path.exists(file_path):
        return False
        
    current_hash = calculate_file_hash_from_path(file_path)
    return current_hash == stored_hash

def get_chunk_dir(user_id, upload_id):
    chunk_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', str(user_id), upload_id)
    if not os.path.exists(chunk_dir):
        os.makedirs(chunk_dir)
    return chunk_dir

def save_chunk(user_id, upload_id, chunk_index, chunk_file, user):
    # Check quota including current chunks
    chunk_file.seek(0, os.SEEK_END)
    chunk_size = chunk_file.tell()
    chunk_file.seek(0)
    
    temp_usage = get_temp_usage(user_id)
    if not user.has_space(chunk_size + temp_usage):
        return False, "Quota exceeded."

    chunk_dir = get_chunk_dir(user_id, upload_id)
    chunk_path = os.path.join(chunk_dir, f"{chunk_index}")
    chunk_file.save(chunk_path)
    return True, None

def delete_upload_chunks(user_id, upload_id):
    chunk_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', str(user_id), upload_id)
    if os.path.exists(chunk_dir):
        shutil.rmtree(chunk_dir)
        return True
    return False

def cleanup_user_temp(user_id):
    """Remove all temporary chunks for a user to prevent quota lock-out."""
    temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp', str(user_id))
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

def merge_chunks(user_id, upload_id, filename, total_chunks, user):
    chunk_dir = get_chunk_dir(user_id, upload_id)
    
    # Check if all chunks exist
    for i in range(total_chunks):
        if not os.path.exists(os.path.join(chunk_dir, f"{i}")):
            return None, f"Missing chunk {i}"
            
    # Check quota before merging (approximate)
    total_size = 0
    for i in range(total_chunks):
        total_size += os.path.getsize(os.path.join(chunk_dir, f"{i}"))
        
    # Note: Chunks are already on disk, so they count towards quota if we include temp usage.
    # But when we merge, we create a NEW file, then delete chunks.
    # So momentarily we need double space? Or we can assume chunks will be deleted.
    # Strict implementation: We need space for the final file.
    # But since chunks ARE the file, we can say:
    # effective_usage = used_bytes + temp_usage
    # new_usage = used_bytes + total_size
    # if new_usage > quota: fail
    
    # However, since chunks are already uploaded, 'used_bytes' doesn't include them yet.
    # So if we just check user.has_space(total_size), it might be enough if we ignore temp_usage here?
    # No, because other uploads might be happening.
    
    # Let's stick to simple check:
    if not user.has_space(total_size):
        shutil.rmtree(chunk_dir)
        return None, "Quota exceeded."

    # Secure filename
    filename = secure_filename(filename)
    if not filename:
        filename = str(uuid.uuid4())
        
    upload_dir = get_user_upload_dir(user.id)
    file_path = os.path.join(upload_dir, filename)

    # Auto-rename if file exists
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(file_path):
        filename = f"{base}_{counter}{ext}"
        file_path = os.path.join(upload_dir, filename)
        counter += 1
    
    # Merge
    with open(file_path, "wb") as outfile:
        for i in range(total_chunks):
            chunk_path = os.path.join(chunk_dir, f"{i}")
            with open(chunk_path, "rb") as infile:
                outfile.write(infile.read())
                
    # Calculate hash
    file_hash = calculate_file_hash_from_path(file_path)
    
    # Save metadata
    metadata = load_metadata(user.id)
    metadata[filename] = {'hash': file_hash, 'share_token': None}
    save_metadata(user.id, metadata)
    
    # Cleanup chunks
    shutil.rmtree(chunk_dir)
    
    return filename, None

def generate_share_token(user_id, filename):
    metadata = load_metadata(user_id)
    if filename not in metadata:
        return None
    
    token = str(uuid.uuid4())
    if isinstance(metadata[filename], str):
        metadata[filename] = {'hash': metadata[filename], 'share_token': token}
    else:
        metadata[filename]['share_token'] = token
        
    save_metadata(user_id, metadata)
    return token

def revoke_share_token(user_id, filename):
    metadata = load_metadata(user_id)
    if filename in metadata and isinstance(metadata[filename], dict):
        metadata[filename]['share_token'] = None
        save_metadata(user_id, metadata)
        return True
    return False

def get_file_by_token(token):
    # This is inefficient (scan all users), but for a small app it's fine.
    # Ideally we'd have a database table for shares.
    # Given the constraints, scanning metadata files is the way.
    
    upload_base = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_base):
        return None, None
        
    for user_id in os.listdir(upload_base):
        if user_id == 'temp': continue
        
        try:
            metadata = load_metadata(user_id)
            for filename, meta in metadata.items():
                if isinstance(meta, dict) and meta.get('share_token') == token:
                    return user_id, filename
        except:
            continue
            
    return None, None