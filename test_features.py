import unittest
import os
import shutil
from app import create_app, db
from app.models import User
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = 'test_uploads_features'
    RATELIMIT_ENABLED = False

class FeatureTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        if os.path.exists('test_uploads_features'):
            shutil.rmtree('test_uploads_features')
        os.makedirs('test_uploads_features')

        # Create Admin
        self.admin = User(username='admin', is_admin=True)
        self.admin.set_password('adminpass')
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        if os.path.exists('test_uploads_features'):
            shutil.rmtree('test_uploads_features')

    def login_admin(self):
        self.client.post('/login', data={'username': 'admin', 'password': 'adminpass'})

    def test_admin_change_password(self):
        self.login_admin()
        
        # Wrong current password
        response = self.client.post('/admin_secure_panel_z8x9/change_password', data={
            'current_password': 'wrong',
            'new_password': 'newpass'
        }, follow_redirects=True)
        self.assertIn(b'Incorrect current password', response.data)
        
        # Correct current password
        response = self.client.post('/admin_secure_panel_z8x9/change_password', data={
            'current_password': 'adminpass',
            'new_password': 'newpass'
        }, follow_redirects=True)
        self.assertIn(b'Password updated successfully', response.data)
        
        # Verify new password works
        self.client.get('/logout')
        response = self.client.post('/login', data={'username': 'admin', 'password': 'newpass'}, follow_redirects=True)
        self.assertIn(b'My Files', response.data)

    def test_quota_gb(self):
        self.login_admin()
        
        # Create user with 2 GB
        response = self.client.post('/admin_secure_panel_z8x9/create_user', data={
            'username': 'user2',
            'password': 'password',
            'quota_gb': 2
        }, follow_redirects=True)
        self.assertIn(b'User created', response.data)
        
        u = User.query.filter_by(username='user2').first()
        self.assertEqual(u.quota_bytes, 2 * 1024 * 1024 * 1024)

        # Update quota to 5 GB
        response = self.client.post(f'/admin_secure_panel_z8x9/update_quota/{u.id}', data={
            'quota_gb': 5
        }, follow_redirects=True)
        self.assertIn(b'Quota updated', response.data)
        
        u = User.query.filter_by(username='user2').first()
        self.assertEqual(u.quota_bytes, 5 * 1024 * 1024 * 1024)

    def test_toggle_admin(self):
        self.login_admin()
        
        # Create normal user
        u = User(username='user3')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        
        # Make admin
        response = self.client.post(f'/admin_secure_panel_z8x9/toggle_admin/{u.id}', follow_redirects=True)
        self.assertIn(b'User user3 is now Admin', response.data)
        self.assertTrue(User.query.get(u.id).is_admin)
        
        # Revoke admin
        response = self.client.post(f'/admin_secure_panel_z8x9/toggle_admin/{u.id}', follow_redirects=True)
        self.assertIn(b'User user3 is now User', response.data)
        self.assertFalse(User.query.get(u.id).is_admin)

    def test_self_demote_prevention(self):
        self.login_admin()
        response = self.client.post(f'/admin_secure_panel_z8x9/toggle_admin/{self.admin.id}', follow_redirects=True)
        self.assertIn(b'Cannot change your own admin status', response.data)
        self.assertTrue(User.query.get(self.admin.id).is_admin)

    def test_dark_mode_elements(self):
        response = self.client.get('/login')
        self.assertIn(b'data-theme', response.data)
        self.assertIn(b'theme-toggle', response.data)

if __name__ == '__main__':
    unittest.main()
