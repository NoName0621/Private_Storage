from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, abort
from flask_login import login_required, current_user
from .utils import save_file, get_user_files, delete_user_file, get_user_upload_dir, verify_file_integrity
from .models import db, User
from werkzeug.utils import secure_filename
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    files = get_user_files(current_user.id)
    return render_template('dashboard.html', files=files, user=current_user)

@main_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'status': 'error', 'message': 'No file part'}, 400
        flash('No file part', 'danger')
        return redirect(url_for('main.dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'status': 'error', 'message': 'No selected file'}, 400
        flash('No selected file', 'danger')
        return redirect(url_for('main.dashboard'))
        
    try:
        # Lock user row to prevent race condition
        user = User.query.with_for_update().get(current_user.id)
        
        filename, error = save_file(file, user)
        if error:
            db.session.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {'status': 'error', 'message': error}, 400
            flash(error, 'danger')
        else:
            # Update used bytes
            file.seek(0, os.SEEK_END)
            size = file.tell()
            user.used_bytes += size
            db.session.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {'status': 'success', 'message': 'File uploaded successfully', 'filename': filename}, 200
            flash('File uploaded successfully.', 'success')
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Upload failed: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'status': 'error', 'message': 'Internal server error'}, 500
        flash('Internal server error during upload.', 'danger')
        
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
        
    try:
        from .utils import save_chunk
        save_chunk(current_user.id, upload_id, int(chunk_index), file)
        return {'status': 'success'}, 200
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@main_bp.route('/upload_merge', methods=['POST'])
@login_required
def upload_merge():
    upload_id = request.form.get('upload_id')
    filename = request.form.get('filename')
    total_chunks = request.form.get('total_chunks')
    
    if not upload_id or not filename or not total_chunks:
        return {'status': 'error', 'message': 'Missing parameters'}, 400
        
    try:
        from .utils import merge_chunks
        
        # Lock user row
        user = User.query.with_for_update().get(current_user.id)
        
        saved_filename, error = merge_chunks(current_user.id, upload_id, filename, int(total_chunks), user)
        
        if error:
            db.session.rollback()
            return {'status': 'error', 'message': error}, 400
            
        # Update used bytes
        # merge_chunks already saved the file, so we can check size
        upload_dir = get_user_upload_dir(current_user.id)
        file_path = os.path.join(upload_dir, saved_filename)
        size = os.path.getsize(file_path)
        
        user.used_bytes += size
        db.session.commit()
        
        flash('File uploaded successfully.', 'success')
        return {'status': 'success', 'filename': saved_filename}, 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Merge failed: {e}")
        return {'status': 'error', 'message': str(e)}, 500

@main_bp.route('/download/<filename>')
@login_required
def download_file(filename):
    # Security check: filename must be secure
    filename = secure_filename(filename)
    
    # Verify integrity
    if not verify_file_integrity(current_user.id, filename):
        flash('File integrity check failed! The file may be corrupted.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    upload_dir = get_user_upload_dir(current_user.id)
    file_path = os.path.join(upload_dir, filename)
    
    # Directory traversal check
    file_path = os.path.abspath(file_path)
    upload_dir = os.path.abspath(upload_dir)
    
    if not file_path.startswith(upload_dir):
        abort(403)
        
    if not os.path.exists(file_path):
        abort(404)

    return send_from_directory(upload_dir, filename, as_attachment=True)

@main_bp.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    if delete_user_file(current_user.id, filename):
        # Update quota
        # We need to know the size of the deleted file to subtract it.
        # But delete_user_file already deleted it.
        # Ideally we should check size before delete.
        # Refactoring logic slightly to handle quota update correctly.
        # But for now, let's just recalculate used_bytes from disk to be safe and self-healing.
        
        # Recalculate usage
        files = get_user_files(current_user.id)
        total_size = sum(f['size'] for f in files)
        current_user.used_bytes = total_size
        db.session.commit()
        
        flash('File deleted.', 'success')
    else:
        flash('File not found.', 'danger')
        
    return redirect(url_for('main.dashboard'))
