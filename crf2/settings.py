import platform
from pathlib import Path

import cx_Oracle
from celery.schedules import crontab

from helpers.helpers import get_config_boolean_value, get_config_value

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
SECRET_KEY = get_config_value("django", "secret_key", raw=True)
DEBUG = get_config_boolean_value("django", "debug")
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
CANVAS_ENVIRONMENT = "PRODUCTION"
ALLOWED_HOSTS = ["*", "localhost"]
INTERNAL_IPS = ["127.0.0.1"]
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
LOGOUT_REDIRECT_URL = (
    "/Shibboleth.sso/Logout?return=https://idp.pennkey.upenn.edu/logout"
)
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "course/static/emails"
EMAIL_USE_TLS = True
EMAIL_PORT = 587
INSTALLED_APPS = [
    "dal",
    "dal_select2",
    "django.contrib.admin",
    "django.contrib.admindocs",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "course",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "admin_auto_filters",
    "django_celery_beat",
    "django_extensions",
    "rest_framework_swagger",
    "debug_toolbar",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "crf2.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "course.context_processors.user_permissions",
            ],
        },
    },
]
WSGI_APPLICATION = "crf2.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"timeout": 20},
    }
}
CORS_ORIGIN_ALLOW_ALL = True
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
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
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_L10N = True
USE_TZ = True
TIME_ZONE = "America/New_York"
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PAGINATION_CLASS": "drf_link_header_pagination.LinkHeaderPagination",
    "PAGE_SIZE": 30,
}

if not DEBUG:
    MIDDLEWARE += ["django.contrib.auth.middleware.RemoteUserMiddleware"]
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.RemoteUserBackend",
    ]

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.logging.LoggingPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]
CELERY_BROKER_URL = "redis://localhost:6379"
CELERY_RESULT_BACKEND = "redis://localhost:6379"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"
CELERY_BEAT_SCHEDULE = {
    "read_canvas_sites": {
        "task": "course.tasks.process_canvas",
        "schedule": crontab(minute="0", hour="0"),
    },
    "clear_canceled_requests": {
        "task": "course.tasks.remove_canceled",
        "schedule": crontab(minute="*/60"),
    },
    "process_approved_requests": {
        "task": "course.tasks.create_canvas_site",
        "schedule": crontab(minute="*/20"),
    },
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "large": {
            "format": (
                "%(asctime)s %(levelname)s %(process)d %(pathname)s %(funcName)s"
                " %(lineno)d %(message)s"
            )
        },
        "tiny": {"format": "%(asctime)s  %(message)s  "},
    },
    "handlers": {
        "errors_file": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": "midnight",
            "interval": 1,
            "filename": "logs/ErrorLoggers.log",
            "formatter": "large",
        },
        "info_file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "when": "midnight",
            "interval": 1,
            "filename": "logs/InfoLoggers.log",
            "formatter": "large",
        },
    },
    "loggers": {
        "error_logger": {
            "handlers": ["errors_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "info_logger": {
            "handlers": ["info_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

if DEBUG:
    INSTALLED_APPS.append("livereload")
    MIDDLEWARE.append("livereload.middleware.LiveReloadScript")

if platform.system() == "Darwin":
    lib_dir = get_config_value("cx_oracle", "lib_dir")
    lib_dir = Path.home() / lib_dir
    cx_Oracle.init_oracle_client(lib_dir=str(lib_dir))
