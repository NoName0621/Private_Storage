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
    UPLOAD_FOLDER = 'test_uploads'
    RATELIMIT_ENABLED = False # Disable for functional tests, enable for specific rate limit test

class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        if os.path.exists('test_uploads'):
            shutil.rmtree('test_uploads')
        os.makedirs('test_uploads')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        if os.path.exists('test_uploads'):
            shutil.rmtree('test_uploads')

    def test_user_creation(self):
        u = User(username='testuser', quota_bytes=1000)
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        self.assertTrue(u.check_password('password'))
        self.assertFalse(u.check_password('wrong'))

    def test_login_logout(self):
        u = User(username='testuser')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()

        response = self.client.post('/login', data={'username': 'testuser', 'password': 'password'}, follow_redirects=True)
        self.assertIn(b'My Files', response.data)

        response = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'Login', response.data)

    def test_file_upload_quota(self):
        u = User(username='testuser', quota_bytes=10) # 10 bytes quota
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        self.client.post('/login', data={'username': 'testuser', 'password': 'password'})

        # Create dummy file > 10 bytes
        data = {'file': (open(__file__, 'rb'), 'test.txt')} # This file is definitely > 10 bytes
        response = self.client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Quota exceeded', response.data)

    def test_file_upload_extension(self):
        u = User(username='testuser', quota_bytes=1000000)
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        self.client.post('/login', data={'username': 'testuser', 'password': 'password'})

        # Create dummy file with bad extension
        from io import BytesIO
        data = {'file': (BytesIO(b'test'), 'test.exe')}
        response = self.client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Invalid file type', response.data)

    def test_admin_access(self):
        # Normal user
        u = User(username='user')
        u.set_password('password')
        db.session.add(u)
        db.session.commit()
        self.client.post('/login', data={'username': 'user', 'password': 'password'})
        
        response = self.client.get('/admin_secure_panel_z8x9/')
        self.assertEqual(response.status_code, 404) # Should be hidden/forbidden

        # Admin user
        admin = User(username='admin', is_admin=True)
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()
        self.client.post('/login', data={'username': 'admin', 'password': 'password'})
        
        response = self.client.get('/admin_secure_panel_z8x9/')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
