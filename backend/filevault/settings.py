"""
Django settings for filevault project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'files',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'filevault.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'filevault.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# CORS settings
# Allow frontend URL from environment variable, or use localhost for development
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# Default allowed origins for local development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add frontend URL from environment variable (for production)
if FRONTEND_URL and FRONTEND_URL not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(FRONTEND_URL)

# In development (DEBUG=True), allow all origins for easier testing
# In production (DEBUG=False), only allow specific origins from CORS_ALLOWED_ORIGINS
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # Production: only allow specified origins
    CORS_ALLOW_CREDENTIALS = True
    # Ensure we have at least one origin
    if not CORS_ALLOWED_ORIGINS and FRONTEND_URL:
        CORS_ALLOWED_ORIGINS = [FRONTEND_URL]

# The browser must be allowed to send the UserId header and read Retry-After.
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = (*default_headers, 'userid')
CORS_EXPOSE_HEADERS = ['Retry-After']

# REST Framework settings
REST_FRAMEWORK = {
    # Callers identify themselves with a `UserId` header; requests without one get 401.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'files.authentication.UserIdHeaderAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Per-user API call limit (see RATE_LIMIT_* below).
    'DEFAULT_THROTTLE_CLASSES': [
        'files.throttling.UserCallRateThrottle',
    ],
    'EXCEPTION_HANDLER': 'files.exceptions.api_exception_handler',
    'UNAUTHENTICATED_USER': None,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# The rate limiter keeps its counters in the cache. LocMem is per process, which is
# right for a single server process; with several workers/hosts use Redis instead.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'file-vault',
    }
}

# --- File Vault limits (override with environment variables) ---
# API calls allowed per user per window. Default: 2 calls per second.
RATE_LIMIT_CALLS = int(os.environ.get('RATE_LIMIT_CALLS', '2'))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('RATE_LIMIT_WINDOW_SECONDS', '1'))
# Physical storage allowed per user, in bytes. Default: 10 MB. Duplicates don't count.
USER_STORAGE_LIMIT_BYTES = int(os.environ.get('USER_STORAGE_LIMIT_BYTES', str(10 * 1024 * 1024)))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'files': {'handlers': ['console'], 'level': os.environ.get('FILES_LOG_LEVEL', 'INFO')},
    },
}

