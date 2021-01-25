"""
Minimal settings file to develop django-ses-sns-tracker.
Use `settings_local.py` to override any settings.
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '4ysv*2#57v%8w!etrjxv=%kAliVB%F/&9=^ih4$njj91to&ar+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

BASE_URL = 'http://localhost:8000'

# Application definition

INSTALLED_APPS = [
    # project
    'test_app',

    # wagtail_to_ion
    'wagtail_to_ion',
    'wagtailmedia',

    # wagtail
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail.core',
    'modelcluster',
    'taggit',
    'rest_framework',

    # django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # wagtail
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
]

ROOT_URLCONF = 'test_proj.urls'

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

WSGI_APPLICATION = 'test_proj.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wagtail_to_ion_dev',
    }
}


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'

# wagtail
WAGTAIL_SITE_NAME = 'Wagtail to ION test project'
WAGTAIL_I18N_ENABLED = False
WAGTAIL_MODERATION_ENABLED = False

# wagtailmedia
WAGTAILDOCS_DOCUMENT_MODEL = 'test_app.IonDocument'
WAGTAILIMAGES_IMAGE_MODEL = 'test_app.IonImage'
WAGTAILMEDIA_MEDIA_MODEL = 'test_app.IonMedia'


# wagtail_to_ion
GET_PAGES_BY_USER = False
ION_ALLOW_MISSING_FILES = False
ION_VIDEO_RENDITIONS = {
    '720p': {
        'video': {
            'codec': 'libx264',
            'size': [-1, 720],
            'method': 'crf',
            'method_parameter': 28,
            'preset': 'slow',
        },
        'audio': {
            'codec': 'aac',
            'bitrate': 96,
        },
        'container': 'mp4',
    },
    '1080p': {
        'video': {
            'codec': 'libx264',
            'size': [-1, 1080],
            'method': 'crf',
            'method_parameter': 28,
            'preset': 'slow',
        },
        'audio': {
            'codec': 'aac',
            'bitrate': 128,
        },
        'container': 'mp4',
    },
}

# ION_READ_ONLY_GROUPS =

ION_COLLECTION_MODEL = 'test_app.IonCollection'
ION_LANGUAGE_MODEL = 'test_app.IonLanguage'
ION_IMAGE_RENDITION_MODEL = 'test_app.IonRendition'
ION_MEDIA_RENDITION_MODEL = 'test_app.IonMediaRendition'
ION_CONTENT_TYPE_DESCRIPTION_MODEL = 'test_app.ContentTypeDescription'

# local setting overrides
try:
    from .settings_local import *  # NOQA
except ImportError:
    pass
