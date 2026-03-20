from pathlib import Path
import os
from dotenv import load_dotenv
try:
    from celery.schedules import crontab
except ImportError:
    crontab = None  # Celery not installed; runserver works without it

# Load .env file from django-docker-compose directory (parent of RoyaltyWebsite)
ENV_DIR = Path(__file__).resolve().parent.parent.parent  # django-docker-compose
ENV_PATH = ENV_DIR / ".env"
COIN_ENV_PATH = ENV_DIR / "coin.env"
# Preserve SERVER if already set (e.g. run_local_with_db4.sh exports SERVER=LOCAL)
_env_server_before = os.getenv("SERVER")
# Also check /app/.env for Docker container
ENV_PATH_DOCKER = Path("/app/.env")
if ENV_PATH_DOCKER.exists():
    load_dotenv(ENV_PATH_DOCKER, override=True)
# Load coin.env first (shared defaults), then .env so local overrides win
if COIN_ENV_PATH.exists():
    load_dotenv(COIN_ENV_PATH, override=True)
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)
if _env_server_before:
    os.environ["SERVER"] = _env_server_before
# Local run: run_local.sh writes this so SQLite is used. Only load it if SERVER not already set
# (so .env with SERVER=LOCAL and db4 credentials is not overridden).
_env_run_local = ENV_DIR / ".env.run_local"
if _env_run_local.exists() and not os.getenv("SERVER"):
    load_dotenv(_env_run_local, override=True)
if not os.getenv("SECRET_KEY"):
    load_dotenv(override=True)  # Fallback to current directory
# Fallback: if Sonosuite vars missing (common when gunicorn runs from different cwd), try ~/.env
if not (os.getenv("SONOSUITE_ADMIN_EMAIL") and os.getenv("SONOSUITE_ADMIN_PASSWORD")):
    _home_env = Path.home() / ".env"
    if _home_env.exists():
        load_dotenv(_home_env, override=True)

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = True
AUTH_USER_MODEL = "main.CDUser"
ALLOWED_HOSTS = ["*"]
ALLOWED_ORIGINS = ["*"]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

INSTALLED_APPS = [
   
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "main",
    "releases",
    "storages",
    # "app_models",
]

CSRF_TRUSTED_ORIGINS = [
    'https://royalties.coindigital.in',
    'http://royalties.coindigital.in',
    'http://localhost:8000',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    #    'django.middleware.csrf.CsrfViewMiddleware',
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "RoyaltyWebsite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django_settings_export.settings_export",
                "main.context_processors.user_role",
            ],
        },
    },
]

WSGI_APPLICATION = "RoyaltyWebsite.wsgi.application"

SERVER = os.getenv("SERVER")
if SERVER == "LOCAL_SQLITE":
    # Run locally with SQLite (no MySQL needed). DB file: RoyaltyWebsite/db.sqlite3
    print("SERVER is LOCAL (SQLite)")
    _sqlite_dir = Path(__file__).resolve().parent.parent
    _sqlite_path = _sqlite_dir / "db.sqlite3"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(_sqlite_path),
        },
        "db2": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(_sqlite_dir / "db2.sqlite3"),
        }
    }
    DB_PRODUCTION_CONNECTION = None
elif SERVER == "LOCAL":
    print("SERVER is LOCAL (MySQL)")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "db4",
            "USER": os.getenv("LOCAL_DB_USER"),
            "PASSWORD": os.getenv("LOCAL_DB_PASSWORD"),
            "HOST": os.getenv("LOCAL_DB_HOST"),
            "PORT": "3306",
        },
        "db2": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "db2",
            "USER": os.getenv("LOCAL_DB_USER"),
            "PASSWORD": os.getenv("LOCAL_DB_PASSWORD"),
            "HOST": os.getenv("LOCAL_DB_HOST"),
            "PORT": "3306",
        }
    }
    DB_PRODUCTION_CONNECTION = os.getenv("LOCAL_DB_PRODUCTION_CONNECTION")
elif SERVER == "EC2":
    print("SERVER is EC2")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "db4",
            "USER": os.getenv("EC2_DB_USER"),
            "PASSWORD": os.getenv("EC2_DB_PASSWORD"),
            "HOST": os.getenv("EC2_DB_HOST"),
            "PORT": "3306",
        },
        "db2": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "db2",
            "USER": os.getenv("EC2_DB_USER"),
            "PASSWORD": os.getenv("EC2_DB_PASSWORD"),
            "HOST": os.getenv("EC2_DB_HOST"),
            "PORT": "3306",
        }
    }
    DB_PRODUCTION_CONNECTION = os.getenv("EC2_DB_PRODUCTION_CONNECTION")
else:
    print("SERVER is REMOTE")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "db4",
            "USER": os.getenv("REMOTE_DB_USER"),
            "PASSWORD": os.getenv("REMOTE_DB_PASSWORD"),
            "HOST": os.getenv("REMOTE_DB_HOST"),
            "PORT": "3306",
        },
        "db2": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "db2",
            "USER": os.getenv("REMOTE_DB_USER"),
            "PASSWORD": os.getenv("REMOTE_DB_PASSWORD"),
            "HOST": os.getenv("REMOTE_DB_HOST"),
            "PORT": "3306",
        }
    }
    DB_PRODUCTION_CONNECTION = os.getenv("REMOTE_DB_PRODUCTION_CONNECTION")

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    _db_path = DATABASES["default"]["NAME"]
    RAW_MYSQL_CONNECTION = f"sqlite:///{_db_path}"
else:
    RAW_MYSQL_CONNECTION = f"mysql://{DATABASES['default']['USER']}:{DATABASES['default']['PASSWORD']}@{DATABASES['default']['HOST']}:{DATABASES['default']['PORT']}/{DATABASES['default']['NAME']}?charset=utf8"

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

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")] if os.path.exists(os.path.join(BASE_DIR, "static")) else []

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

ADMINS = ()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}

ELASTIC_EMAIL_SERVICE_API_KEY = os.getenv("ELASTIC_EMAIL_SERVICE_API_KEY")

# aws settings
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = "us-west-1"
AWS_S3_FILE_OVERWRITE = True
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_EXPIRE = 157784630
AWS_S3_ADDRESSING_STYLE = "virtual"
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
EMAIL_BACKEND = "django_ses.SESBackend"


# Code for handling multiple deployments

WEBAPP_NAME = os.getenv("WEBAPP_NAME")
LOGO = {
    "normal": os.getenv("LOGO_NORMAL"),
    "light": os.getenv("LOGO_LIGHT"),
    "dark": os.getenv("LOGO_DARK"),
}
DOMAIN_URL_ = os.getenv("DOMAIN_URL_")

SETTINGS_EXPORT = [
    "WEBAPP_NAME",
    "LOGO",
]

SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
DEPLOYMENT_EMAIL = os.getenv("DEPLOYMENT_EMAIL")
EMAIL_FROM = os.getenv("EMAIL_FROM")

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# Swagger settings
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'basic': {
            'type': 'basic'
        }
    },
    'USE_SESSION_AUTH': True,
    'SECURITY_REQUIREMENTS': [{'basic': []}],
}

# Celery (async DDEX generation; broker = Redis)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
# Optional: run DDEX batch daily at 2:00 AM (only when Celery is installed)
CELERY_BEAT_SCHEDULE = {}
if crontab is not None:
    CELERY_BEAT_SCHEDULE = {
        "ddex-batch-daily": {
            "task": "releases.tasks.build_ddex_batch_task",
            "schedule": crontab(hour=2, minute=0),
            "kwargs": {
                "since_date": None,
                "status_filter": "approved",
                "limit": 0,
                "output_base": "ddex_output",
            },
        },
    }