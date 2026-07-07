import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'surface-django-dev-key-2024')
SURFACE_TOKEN_SECRET = os.environ.get('SECRET', 'surface-dev-key-2024')

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "surface.pythonanywhere.com", "www.surfacedive.app"]
APPEND_SLASH = False

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() != 'false'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Surface <noreply@surface.app>')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'api',
]

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'surface.urls'
WSGI_APPLICATION = 'surface.wsgi.application'

# Database: MySQL when db_credentials.json is present (production),
# sqlite otherwise (local development). db_credentials.json is git-ignored;
# see db_credentials.json.example for the expected format.
DB_CREDENTIALS_FILE = BASE_DIR / 'db_credentials.json'

if DB_CREDENTIALS_FILE.exists():
    with open(DB_CREDENTIALS_FILE) as f:
        _db_credentials = json.load(f)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': _db_credentials['NAME'],
            'USER': _db_credentials['USER'],
            'PASSWORD': _db_credentials['PASSWORD'],
            'HOST': _db_credentials['HOST'],
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {'init_command': 'PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;'},
        }
    }

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
