"""
Django settings for crf2 project.

Generated by 'django-admin startproject' using Django 2.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
from configparser import ConfigParser
import django_heroku


config = ConfigParser()
config.read('config/config.ini')




# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("basedir",BASE_DIR)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config.get('django','secret_key',raw=True)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

CANVAS_ENVIRONMENT = 'TEST' # Could be 'BETA', or 'PRODUCTION'
#
ALLOWED_HOSTS = ['*','localhost']#'128.91.177.58'
#]
INTERNAL_IPS = [
    # ...
    '127.0.0.1',
    # ...
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/
URL_PREFIX = '/siterequest'
STATIC_URL = URL_PREFIX+'/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static")#'/Users/mfhodges/Desktop/CRF2/course/static'#os.path.join(BASE_DIR, "static")

LOGIN_REDIRECT_URL = URL_PREFIX
LOGOUT_REDIRECT_URL = '/Shibboleth.sso/Logout?return=https://idp.pennkey.upenn.edu/logout'


EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = 'course/static/emails' # change this to a proper location
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # to have it sent to console
#EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' # to actually use it
EMAIL_USE_TLS = True
#EMAIL_HOST = config.get('email', 'emailhost')
EMAIL_PORT = 587
#EMAIL_HOST_USER = config.get('email', 'emailhostuser')
#EMAIL_HOST_PASSWORD = config.get('email', 'password')
#DEFAULT_FROM_EMAIL = config.get('email', 'defaultfromemail')

"""
# For Django shib
AUTHENTICATION_BACKENDS += (
    'shibboleth.backends.ShibbolethRemoteUserBackend',
)

SHIBBOLETH_ATTRIBUTE_MAP = {
    "shib-user": (True, "username"),
    "shib-given-name": (False, "first_name"),
    "shib-sn": (False, "last_name"),
    "shib-mail": (False, "email"),
}
LOGIN_URL = ''
#'https://weblogin.pennkey.upenn.edu/login?factors=UPENN.EDU&cosign-pennkey-idp-0&https://idp.pennkey.upenn.edu/idp/Authn/RemoteUser?conversation=e1s1'
"""
# Application definition
INSTALLED_APPS = [
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
	'course',
	'rest_framework',
    'corsheaders',
    'django_filters',
    'admin_auto_filters',
    'django_celery_beat',
    'django_extensions',
    'rest_framework_swagger',
    'debug_toolbar',
    #'shibboleth',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
     'debug_toolbar.middleware.DebugToolbarMiddleware',
    #'shibboleth.middleware.ShibbolethRemoteUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

]

ROOT_URLCONF = 'crf2.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates')
        ],
        'APP_DIRS': True, #why does this disagree with 'loaders'
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                 "course.context_processors.user_permissons"
            ],
        #    'loaders': [
        #    ('django.template.loaders.cached.Loader', [
        #        'django.template.loaders.filesystem.Loader',
        #        'django.template.loaders.app_directories.Loader',
        #    ]),
        #],
            #'libraries':{
            #'template_extra'
            #}
        },
    },
]

WSGI_APPLICATION = 'crf2.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

CORS_ORIGIN_ALLOW_ALL = True

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'



USE_I18N = True

USE_L10N = True


USE_TZ = True
TIME_ZONE = 'America/New_York'


REST_FRAMEWORK = {
#    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAdminUser','rest_framework.permissions.IsAuthenticated'),
#    'DEFAULT_AUTHENTICATION_CLASSES': (
#        'rest_framework.authentication.BasicAuthentication',
#        'rest_framework.authentication.SessionAuthentication',
#    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        #'rest_framework.renderers.TemplateHTMLRenderer', # this line messes up the browsable api
        #'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_FILTER_BACKENDS': ('rest_framework.filters.SearchFilter','django_filters.rest_framework.DjangoFilterBackend',),
    #'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'DEFAULT_PAGINATION_CLASS': 'drf_link_header_pagination.LinkHeaderPagination',
    'PAGE_SIZE': 30,
    #'EXCEPTION_HANDLER': 'course.views.custom_exception_handler'

    #'DEFAULT_PARSER_CLASSES': (
    #    'rest_framework.parsers.JSONParser',
    #)

}

if DEBUG == False:
    MIDDLEWARE += ['django.contrib.auth.middleware.RemoteUserMiddleware']
    AUTHENTICATION_BACKENDS = [
        'django.contrib.auth.backends.RemoteUserBackend',
    ]
    #

DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
]


from celery.schedules import crontab

# Celery application definition
#
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
# Other Celery settings

CELERY_BEAT_SCHEDULE = {
    'task-number-one': {
        'task': 'course.tasks.task_process_approved',
        'schedule': crontab(minute='*/1')#,
        #'args': (*args)
    }
}
CELERY_BEAT_SCHEDULER: 'django_celery_beat.schedulers:DatabaseScheduler'


#django_heroku.settings(locals())



# importing logger settings
try:
    from .logger_settings import *
except Exception as e:

    # in case of any error, pass silently.
    pass
