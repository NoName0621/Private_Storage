from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from .models import User, db
from .utils import validate_password

admin_bp = Blueprint('admin', __name__, url_prefix='/admin_secure_panel_z8x9')

@admin_bp.before_request
def restrict_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(404) # Hide existence

@admin_bp.route('/')
def index():
    users = User.query.all()
    return render_template('admin.html', users=users)

@admin_bp.route('/create_user', methods=['POST'])
def create_user():
    username = request.form.get('username')
    password = request.form.get('password')
    quota_gb = request.form.get('quota_gb', type=int)
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin.index'))
        
    is_valid, error = validate_password(password)
    if not is_valid:
        flash(error, 'danger')
        return redirect(url_for('admin.index'))

    user = User(username=username, quota_bytes=quota_gb * 1024 * 1024 * 1024)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    flash('User created.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/update_quota/<int:user_id>', methods=['POST'])
def update_quota(user_id):
    user = User.query.get_or_404(user_id)
    quota_gb = request.form.get('quota_gb', type=int)
    user.quota_bytes = quota_gb * 1024 * 1024 * 1024
    db.session.commit()
    flash('Quota updated.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/change_password', methods=['POST'])
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    
    if not current_user.check_password(current_password):
        flash('Incorrect current password.', 'danger')
        return redirect(url_for('admin.index'))
        
    is_valid, error = validate_password(new_password)
    if not is_valid:
        flash(error, 'danger')
        return redirect(url_for('admin.index'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password updated successfully.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/toggle_admin/<int:user_id>', methods=['POST'])
def toggle_admin(user_id):
    if user_id == current_user.id:
        flash('Cannot change your own admin status.', 'danger')
        return redirect(url_for('admin.index'))
        
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = "Admin" if user.is_admin else "User"
    flash(f'User {user.username} is now {status}.', 'success')
    return redirect(url_for('admin.index'))
