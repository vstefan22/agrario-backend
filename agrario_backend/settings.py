'''DEFINE SETTINGS FOR DJANGO PROJECT'''

import os
import json
from pathlib import Path
from datetime import timedelta
import dj_database_url

import firebase_admin
from firebase_admin import credentials

from dotenv import load_dotenv
from google.oauth2 import service_account

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False')
FRONTEND_URL = os.getenv('FRONTEND_URL')
BACKEND_URL = os.getenv('BACKEND_URL')

ALLOWED_HOSTS = ["127.0.0.1"]


CSRF_TRUSTED_ORIGINS = [FRONTEND_URL, BACKEND_URL]
CORS_ALLOWED_ORIGINS = [
    FRONTEND_URL,
    BACKEND_URL,
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)


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

    # DRF
    'rest_framework',
    'corsheaders',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # CORS
    "corsheaders.middleware.CorsMiddleware",
]

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


# FIREBASE AUTH
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_JSON_PATH")

if firebase_credentials_path and os.path.exists(firebase_credentials_path):
    print('WRONG!')
    with open(firebase_credentials_path, 'r') as f:
        credentials_info = json.load(f)
elif os.getenv("FIREBASE_CREDENTIALS_JSON"):
    print('CORRECT!')
    credentials_info = json.loads(os.getenv("FIREBASE_CREDENTIALS_JSON"))
else:
    raise Exception("Firebase credentials not provided.")

if not firebase_admin._apps:
    cred = credentials.Certificate(credentials_info)
    firebase_admin.initialize_app(cred)


STATIC_URL = '/static/'
google_credentials_path = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH")
if google_credentials_path and os.path.exists(google_credentials_path):
    with open(google_credentials_path, 'r') as f:
        credentials_info = json.load(f)
    GS_CREDENTIALS = service_account.Credentials.from_service_account_info(
        credentials_info)
else:
    google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if (google_credentials_json):
        credentials_info = json.loads(google_credentials_json)
        GS_CREDENTIALS = service_account.Credentials.from_service_account_info(
            credentials_info)

    else:
        raise Exception(
            "Google Cloud credentials path is not set in the environment.")

STORAGES = {
    # FOR MEDIA FILES
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "project_id": os.getenv("G_CLOUD_PROJECT_ID"),
            "bucket_name": os.getenv("G_CLOUD_BUCEKT_NAME_MEDIA"),
            "file_overwrite": False,
            "credentials": GS_CREDENTIALS,
            "expiration": timedelta(seconds=120)
        },
    },
    # FOR STATIC FILES
    "staticfiles": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "project_id": os.getenv("G_CLOUD_PROJECT_ID"),
            # Use a different bucket for static files
            "bucket_name": os.getenv("G_CLOUD_BUCEKT_NAME_STATIC"),
            "credentials": GS_CREDENTIALS,
        },
    },
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
