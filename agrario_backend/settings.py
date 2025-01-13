"""Django settings for the Agrario project.
This file contains configuration for the project, including
installed apps, middleware, database connections, and third-party integrations.
"""

import base64
import json
import logging
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from google.oauth2 import service_account
import logging

# Load environment variables
load_dotenv()
# django_heroku.settings(locals())

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

FRONTEND_URL = os.getenv('FRONTEND_URL')
BACKEND_URL = os.getenv('BACKEND_URL')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')

ANALYSE_PLUS_RATE = 2

ALLOWED_HOSTS = ['127.0.0.1',
                'agrario-backend-cc0a3b9c6ae6.herokuapp.com',
                'localhost']


CSRF_TRUSTED_ORIGINS = [FRONTEND_URL, BACKEND_URL]
CORS_ALLOWED_ORIGINS = [FRONTEND_URL, BACKEND_URL]
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)

# Swagger settings
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Token": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
        },
    },
    "USE_SESSION_AUTH": False,
    "DEFAULT_AUTO_SCHEMA_CLASS": "drf_yasg.inspectors.SwaggerAutoSchema",
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

    # DRF
    'rest_framework',
    'corsheaders',
    'rest_framework.authtoken',
    'drf_yasg',
    'django_filters',

    # custom apps
    'accounts',
    'offers',
    'payments',
    'subscriptions',
    'reports',
    'messaging',
    'invites', 
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'accounts.firebase_auth.FirebaseAuthentication',
        'accounts.firebase_auth.FirebaseAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        # 'rest_framework.permissions.IsAuthenticated',
    ],
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# URLs and templates
ROOT_URLCONF = "agrario_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "agrario_backend.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases




# Database
if DEBUG:
    # POSTGRESQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': os.getenv("DATABASE_NAME"),
            'USER': os.getenv("DATABASE_USER"),
            'PASSWORD': os.getenv("DATABASE_PASSWORD"),
            'HOST': os.getenv("DATABASE_HOST"),
            'PORT': os.getenv("DATABASE_PORT"),
        }
    }

# Database
# if not DEBUG:
#     # POSTGRESQL
#     DATABASES = {
#         'default': {
#             'ENGINE': 'django.contrib.gis.db.backends.postgis',
#             'NAME': os.getenv("DATABASE_NAME"),
#             'USER': os.getenv("DATABASE_USER"),
#             'PASSWORD': os.getenv("DATABASE_PASSWORD"),
#             'HOST': os.getenv("DATABASE_HOST"),
#             'PORT': os.getenv("DATABASE_PORT"),
#         }
#     }
# else:
#     DATABASES = {
#         'default': dj_database_url.config(engine='django.contrib.gis.db.backends.postgis')
#     }
AUTH_USER_MODEL = 'accounts.MarketUser'
# Load Firebase credentials
# Load Firebase credentials
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_JSON_PATH")
firebase_credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "your_firebase_api_key_here")

if firebase_credentials_path and os.path.exists(firebase_credentials_path):
    with open(firebase_credentials_path, "r") as f:
        firebase_config = json.load(f)
elif firebase_credentials_base64:
    firebase_config = json.loads(base64.b64decode(firebase_credentials_base64).decode("utf-8"))
else:
    firebase_config = None  # Default to None to handle missing credentials

if firebase_config is None:
    raise Exception("Firebase credentials are not provided.")

# Make firebase_config available to other parts of the app
FIREBASE_CONFIG = firebase_config


# GOOGLE CLOUD
google_credentials_path = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH")
google_credentials_base64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

try:
    if google_credentials_path and os.path.exists(google_credentials_path):
        # Use the credentials file if it exists
        with open(google_credentials_path, "r") as f:
            google_credentials_info = json.load(f)
    elif google_credentials_base64:
        # Decode the Base64 string into JSON
        google_credentials_info = json.loads(
            base64.b64decode(google_credentials_base64).decode("utf-8")
        )
    else:
        raise Exception("Google Cloud credentials not provided.")

    GS_CREDENTIALS = service_account.Credentials.from_service_account_info(
        google_credentials_info
    )

except Exception as e:
    logging.error(f"Error loading Google Cloud credentials: {e}")
    raise

G_CLOUD_PROJECT_ID = os.getenv("G_CLOUD_PROJECT_ID")
G_CLOUD_BUCKET_NAME_MEDIA = os.getenv("G_CLOUD_BUCKET_NAME_MEDIA")
G_CLOUD_BUCKET_NAME_STATIC = os.getenv("G_CLOUD_BUCKET_NAME_STATIC")
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "project_id": os.getenv("G_CLOUD_PROJECT_ID"),
            "bucket_name": os.getenv("G_CLOUD_BUCKET_NAME_MEDIA"),
            "credentials": GS_CREDENTIALS,
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "project_id": os.getenv("G_CLOUD_PROJECT_ID"),
            "bucket_name": os.getenv("G_CLOUD_BUCKET_NAME_STATIC"),
            "credentials": GS_CREDENTIALS,
        },
    },
}

GDAL_LIBRARY_PATH = r"C:\Users\merlin\anaconda3\envs\agrario_env\Library\bin\gdal.dll"
GEOS_LIBRARY_PATH  = r"C:\Users\merlin\anaconda3\envs\agrario_env\Library\bin\geos_c.dll"

# Static files configuration
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
