from app import create_app, db
from app.models import User
import os

app = create_app()

def init_db():
    with app.app_context():
        if not os.path.exists('storage.db'):
            db.create_all()
            # Create default admin if not exists
            if not User.query.filter_by(username='admin').first():
                admin = User(username='admin', is_admin=True, quota_bytes=1024*1024*1024) # 1GB
                admin.set_password('admin_password_change_me')
                db.session.add(admin)
                db.session.commit()
                print("Admin user created: admin / admin_password_change_me")

if __name__ == '__main__':
    init_db()
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
