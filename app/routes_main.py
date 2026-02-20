from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, abort
from flask_login import login_required, current_user
from .utils import save_file, get_user_files, delete_user_file, get_user_upload_dir, verify_file_integrity, generate_share_token, revoke_share_token, get_file_by_token, delete_upload_chunks, is_safe_upload_id
from .models import db
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    # Cleanup temp files on dashboard load to prevent quota lock-out from failed uploads
    from .utils import cleanup_user_temp, format_size
    cleanup_user_temp(current_user.id)
    
    subpath = request.args.get('path', '')
    # Security check for subpath (basic) - utils handles the real check
    if '..' in subpath or subpath.startswith('/') or subpath.startswith('\\'):
        subpath = ''
        
    files = get_user_files(current_user.id, subpath)
    
    # Breadcrumbs
    breadcrumbs = []
    if subpath:
        parts = subpath.replace('\\', '/').split('/')
        current_path = ''
        for part in parts:
            if not part: continue
            current_path = os.path.join(current_path, part)
            breadcrumbs.append({'name': part, 'path': current_path.replace('\\', '/')})
            
    return render_template('dashboard.html', files=files, user=current_user, current_path=subpath, breadcrumbs=breadcrumbs)

@main_bp.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    folder_name = request.form.get('folder_name')
    current_path = request.form.get('current_path', '')
    
    if not folder_name:
        flash('Folder name is required.', 'danger')
        return redirect(url_for('main.dashboard', path=current_path))
        
    from .utils import create_user_folder
    success, error = create_user_folder(current_user.id, current_path, folder_name)
    
    if success:
        flash('Folder created successfully.', 'success')
    else:
        flash(f'Error creating folder: {error}', 'danger')
        
    return redirect(url_for('main.dashboard', path=current_path))

@main_bp.route('/preview/zip/<path:filename>')
@login_required
def preview_zip(filename):
    # This route returns JSON content of the zip file
    from .utils import get_zip_contents
    contents = get_zip_contents(current_user.id, filename)
    if contents is None:
         return {'status': 'error', 'message': 'Could not read file'}, 400
    return {'status': 'success', 'contents': contents}, 200

@main_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'status': 'error', 'message': 'No file part'}, 400
        flash('No file part', 'danger')
        return redirect(url_for('main.dashboard'))
    
    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'status': 'error', 'message': 'No selected file'}, 400
        flash('No selected file', 'danger')
        return redirect(url_for('main.dashboard'))
        
    current_path = request.form.get('current_path', '')
    
    for file in files:
        filename, error = save_file(file, current_user, current_path)
        if error:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {'status': 'error', 'message': error}, 400
            flash(error, 'danger')
        else:
            # Update used bytes
            file.seek(0, os.SEEK_END)
            size = file.tell()
            current_user.used_bytes += size
            db.session.commit()
            
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'status': 'success', 'message': 'Files uploaded successfully'}, 200
    flash('Files uploaded successfully.', 'success')
        
    return redirect(url_for('main.dashboard'))

@main_bp.route('/upload_chunk', methods=['POST'])
@login_required
def upload_chunk():
    if 'file' not in request.files:
        return {'status': 'error', 'message': 'No file part'}, 400
        
    file = request.files['file']
    upload_id = request.form.get('upload_id')
    chunk_index = request.form.get('chunk_index')
    
    if not upload_id or chunk_index is None:
        return {'status': 'error', 'message': 'Missing upload_id or chunk_index'}, 400
    if not is_safe_upload_id(upload_id):
        return {'status': 'error', 'message': 'Invalid upload_id'}, 400
        
    try:
        from .utils import save_chunk
        success, error = save_chunk(current_user.id, upload_id, int(chunk_index), file, current_user)
        if not success:
            return {'status': 'error', 'message': error}, 400
        return {'status': 'success'}, 200
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@main_bp.route('/upload_merge', methods=['POST'])
@login_required
def upload_merge():
    upload_id = request.form.get('upload_id')
    filename = request.form.get('filename')
    total_chunks = request.form.get('total_chunks')
    current_path = request.form.get('current_path', '')
    
    if not upload_id or not filename or not total_chunks:
        return {'status': 'error', 'message': 'Missing parameters'}, 400
    if not is_safe_upload_id(upload_id):
        return {'status': 'error', 'message': 'Invalid upload_id'}, 400
        
    try:
        from .utils import merge_chunks
        saved_filename, error = merge_chunks(current_user.id, upload_id, filename, int(total_chunks), current_user, current_path)
        
        if error:
            return {'status': 'error', 'message': error}, 400
            
        # Update used bytes
        upload_dir = get_user_upload_dir(current_user.id)
        target_dir = os.path.join(upload_dir, current_path)
        file_path = os.path.join(target_dir, saved_filename)
        size = os.path.getsize(file_path)
        
        current_user.used_bytes += size
        db.session.commit()
        
        flash('File uploaded successfully.', 'success')
        return {'status': 'success', 'filename': saved_filename}, 200
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@main_bp.route('/upload/cancel', methods=['POST'])
@login_required
def upload_cancel():
    upload_id = request.form.get('upload_id')
    if not upload_id:
        return {'status': 'error', 'message': 'Missing upload_id'}, 400
    if not is_safe_upload_id(upload_id):
        return {'status': 'error', 'message': 'Invalid upload_id'}, 400
        
    if delete_upload_chunks(current_user.id, upload_id):
        return {'status': 'success', 'message': 'Upload cancelled and cleaned up'}, 200
    else:
        return {'status': 'error', 'message': 'Upload not found or already cleaned'}, 404

@main_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    # filename here is actually a path relative to user's root
    # Security check: ensure path stays within user directory
    # utils.get_user_upload_dir handles the base, we need to ensure filename component is safe
    
    # We can rely on send_from_directory for basic traversal protection, 
    # but we should also check our own logic.
    
    # Split path to verify segments if needed, or just rely on secure_filename for the final component?
    # Actually, filename can be "folder/file.txt". fast_safe_join used by send_from_directory is best.
    
    # We need to verify integrity. Our verify_file_integrity might expect just a filename or relative path.
    # Let's check utils.verify_file_integrity. It does: file_path = os.path.join(upload_dir, filename)
    # So if we pass "folder/file.txt", it joins correctly.
    
    if not verify_file_integrity(current_user.id, filename):
        flash('File integrity check failed! The file may be corrupted.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    upload_dir = get_user_upload_dir(current_user.id)
    return send_from_directory(upload_dir, filename, as_attachment=True)

@main_bp.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    if delete_user_file(current_user.id, filename):
        # Recalculate usage
        files = get_user_files(current_user.id)
        total_size = sum(f['size'] for f in files)
        current_user.used_bytes = total_size
        db.session.commit()
        
        flash('File deleted.', 'success')
    else:
        flash('File not found.', 'danger')
        
    return redirect(url_for('main.dashboard'))

@main_bp.route('/delete_folder', methods=['POST'])
@login_required
def delete_folder():
    folder_path = request.form.get('folder_path')
    current_path = request.form.get('current_path', '')
    
    if not folder_path:
        flash('Folder path is required.', 'danger')
        return redirect(url_for('main.dashboard', path=current_path))
        
    from .utils import delete_user_folder
    
    # folder_path coming from form is likely relative to user root, or actually just the folder name if in current_path?
    # In dashboard.html we will pass `file.path` which is relative to user root.
    
    if delete_user_folder(current_user.id, folder_path):
        # Recalculate usage
        # Since we deleted a folder, it's safest to recalculate all
        upload_dir = get_user_upload_dir(current_user.id)
        total_size = 0
        for root, dirs, filenames in os.walk(upload_dir):
            for f in filenames:
                fp = os.path.join(root, f)
                total_size += os.path.getsize(fp)
                
        current_user.used_bytes = total_size
        db.session.commit()
        
        flash('Folder deleted.', 'success')
    else:
        flash('Error deleting folder.', 'danger')
        
    return redirect(url_for('main.dashboard', path=current_path))

@main_bp.route('/share/<filename>', methods=['POST'])
@login_required
def share_file(filename):
    token = generate_share_token(current_user.id, filename)
    if token:
        share_url = url_for('main.public_download', token=token, _external=True)
        return {'status': 'success', 'token': token, 'url': share_url}, 200
    return {'status': 'error', 'message': 'File not found'}, 404

@main_bp.route('/unshare/<filename>', methods=['POST'])
@login_required
def unshare_file(filename):
    if revoke_share_token(current_user.id, filename):
        return {'status': 'success'}, 200
    return {'status': 'error', 'message': 'File not found'}, 404

@main_bp.route('/s/<token>')
def public_download(token):
    user_id, filename = get_file_by_token(token)
    if not user_id or not filename:
        abort(404)
        
    upload_dir = get_user_upload_dir(user_id)
    return send_from_directory(upload_dir, filename, as_attachment=True)
