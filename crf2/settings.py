import os
import platform
from pathlib import Path

from celery.schedules import crontab
from cx_Oracle import init_oracle_client

from config.config import DEBUG_VALUE, LIB_DIR, SECRET_KEY_VALUE
from course.models import User


def get_secret(key, default):
    value = os.getenv(key, default)
    if os.path.isfile(value):
        with open(value) as f:
            return f.read()
    return value


BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
SECRET_KEY = SECRET_KEY_VALUE
DEBUG = DEBUG_VALUE
ALLOWED_HOSTS = ["*"]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
LOGOUT_REDIRECT_URL = (
    "/Shibboleth.sso/Logout?return=https://idp.pennkey.upenn.edu/logout"
)
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
        "DIRS": [str(BASE_DIR / "templates")],
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
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": get_secret("POSTGRES_DATABASE_NAME", "crf"),
        "USER": get_secret("POSTGRES_USER", "crf"),
        "PASSWORD": get_secret("POSTGRES_PASSWORD_FILE", "password"),
        "HOST": "postgres",
        "PORT": get_secret("POSTGRES_PORT", "5432"),
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
        "task": "course.tasks.sync_sites",
        "schedule": crontab(minute="0", hour="0"),
    },
    "clear_canceled_requests": {
        "task": "course.tasks.delete_canceled_requests",
        "schedule": crontab(minute="*/60"),
    },
    "process_approved_requests": {
        "task": "course.tasks.create_canvas_sites",
        "schedule": crontab(minute="*/20"),
    },
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CRF_LOGGER = {
    "handlers": ["crf", "console"],
    "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    "propagate": False,
}
MODULES = [
    "canvas",
    "config",
    "course",
    "crf2",
    "data_warehouse",
    "open_data",
    "report",
]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "[%(levelname)s] %(asctime)s %(filename)s %(funcName)s"
                " %(lineno)d %(message)s"
            )
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
        "crf": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": "logs/crf.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "loggers": {module: CRF_LOGGER for module in MODULES},
}
AUTH_USER_MODEL = User

if DEBUG:
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]
    INSTALLED_APPS.append("django_sass")
    # MIDDLEWARE.append("livereload.middleware.LiveReloadScript")
    CSRF_TRUSTED_ORIGINS = ["https://reqform-local.library.upenn.edu"]
    if platform.system() == "Darwin":
        lib_dir = Path.home() / LIB_DIR
        init_oracle_client(lib_dir=str(lib_dir))
else:  # pragma: no cover
    MIDDLEWARE.append("django.contrib.auth.middleware.RemoteUserMiddleware")
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.RemoteUserBackend",
    ]
