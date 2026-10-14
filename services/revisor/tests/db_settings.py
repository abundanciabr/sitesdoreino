"""Disposable test database only; not deployment settings or a web server."""
import os
SECRET_KEY = 'test-only-not-for-a-server'
INSTALLED_APPS = ['revisor']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
if os.environ.get('REVISOR_TEST_PG_PORT'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql', 'NAME': 'revisor_test',
        'USER': 'postgres', 'PASSWORD': 'disposable-revisor-test',
        'HOST': '127.0.0.1', 'PORT': os.environ['REVISOR_TEST_PG_PORT'],
    }
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
