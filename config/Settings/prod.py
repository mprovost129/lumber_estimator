import os
from .base import *

DEBUG = False

ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')

# Whitenoise - insert after SecurityMiddleware
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Media storage. Render web service filesystems are EPHEMERAL: without one of
# the options below, every deploy wipes uploaded plans and thumbnails.
#   Option A (recommended): S3-compatible object storage. Set
#     AWS_STORAGE_BUCKET_NAME (+ AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY,
#     and AWS_S3_ENDPOINT_URL for Cloudflare R2 / Backblaze B2).
#   Option B: a Render Persistent Disk mounted at MEDIA_ROOT (single
#     instance only). Set MEDIA_ROOT to the disk mount path, e.g. /var/data.
if os.environ.get('AWS_STORAGE_BUCKET_NAME'):
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': {
                'bucket_name': os.environ['AWS_STORAGE_BUCKET_NAME'],
                'endpoint_url': os.environ.get('AWS_S3_ENDPOINT_URL') or None,
                'region_name': os.environ.get('AWS_S3_REGION_NAME') or None,
                'default_acl': 'private',
                'file_overwrite': False,
                'querystring_expire': 3600,
            },
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    MEDIA_ROOT = os.environ.get('MEDIA_ROOT', MEDIA_ROOT)

# Persistent DB connections
CONN_MAX_AGE = 60

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# HTTPS / security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

