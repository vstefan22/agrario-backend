'''DEFINE SETTINGS FOR DJANGO PROJECT'''


from pathlib import Path
import os
import json
import base64
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
import dj_database_url

# Load environment variables
load_dotenv()
# django_heroku.settings(locals())

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-g5jyq%m8oeq9rlmu4zw59^wka1#^gm(x839pg@hikive)9d^7%'

# STRIPE
STRIPE_SECRET_KEY = 'your_stripe_secret_key'  # Replace with actual key
STRIPE_ENDPOINT_SECRET = 'your_stripe_endpoint_secret'  # Replace with actual key


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1",
                 'agrario-backend-cc0a3b9c6ae6.herokuapp.com', 'localhost']

# Authentication settings
AUTH_USER_MODEL = 'accounts.MarketUser'

# CORS and CSRF settings
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL, BACKEND_URL]
CORS_ALLOWED_ORIGINS = [FRONTEND_URL, BACKEND_URL]
CORS_ALLOW_CREDENTIALS = True

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
    'DEFAULT_AUTO_SCHEMA_CLASS': 'drf_yasg.inspectors.SwaggerAutoSchema',
}

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # G-CLOUD
    'storages',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'accounts',
    'offers',
    'drf_yasg',
    # 'django.contrib.gis',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = 'Agrario'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}


ROOT_URLCONF = 'agrario_backend.urls'

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

WSGI_APPLICATION = 'agrario_backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases


# Database
if (DEBUG):
    # POSTGRESQL
    # DATABASES = {
    #     'default': {
    #         'ENGINE': 'django.db.backends.postgresql',
    #         'NAME': os.getenv("DATABASE_NAME"),
    #         'USER': os.getenv("DATABASE_USER"),
    #         'PASSWORD': os.getenv("DATABASE_PASSWORD"),
    #         'HOST': os.getenv("DATABASE_HOST"),
    #         'PORT': os.getenv("DATABASE_PORT"),
    #     }
    # }

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.config()
    }

AUTH_USER_MODEL = 'accounts.MarketUser'
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_JSON_PATH")
firebase_credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")


try:
    if firebase_credentials_path and os.path.exists(firebase_credentials_path):
        with open(firebase_credentials_path, 'r') as f:
            FIREBASE_CREDENTIALS = json.load(f)
    elif firebase_credentials_base64:
        FIREBASE_CREDENTIALS = json.loads(base64.b64decode(
            firebase_credentials_base64).decode('utf-8'))
except Exception as e:
    logging.error(f"Error loading Firebase credentials: {e}")


# Google Cloud configuration
GS_CREDENTIALS = None
google_credentials_path = os.getenv('GOOGLE_CREDENTIALS_JSON_PATH')
google_credentials_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')

try:
    if google_credentials_path and os.path.exists(google_credentials_path):
        with open(google_credentials_path, 'r') as f:
            google_credentials_info = json.load(f)
    elif google_credentials_base64:
        google_credentials_info = json.loads(
            base64.b64decode(google_credentials_base64).decode('utf-8'))
    GS_CREDENTIALS = service_account.Credentials.from_service_account_info(
        google_credentials_info)
except Exception as e:
    logging.error(f"Error loading Google Cloud credentials: {e}")

# Google Cloud settings
STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.gcloud.GoogleCloudStorage',
        'OPTIONS': {
            'project_id': os.getenv('G_CLOUD_PROJECT_ID'),
            'bucket_name': os.getenv('G_CLOUD_BUCKET_NAME_MEDIA'),
            'credentials': GS_CREDENTIALS,
        },
    },
    'staticfiles': {
        'BACKEND': 'storages.backends.gcloud.GoogleCloudStorage',
        'OPTIONS': {
            'project_id': os.getenv('G_CLOUD_PROJECT_ID'),
            'bucket_name': os.getenv('G_CLOUD_BUCKET_NAME_STATIC'),
            'credentials': GS_CREDENTIALS,
        },
    },
}

# Static files configuration
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Password validation
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
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
