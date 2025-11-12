import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# -----------------
# Base / env
# -----------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "fallback-key")
DEBUG = os.getenv("DEBUG", "True") == "True"

# ALLOWED_HOSTS: Support comma-separated environment variable or default list
allowed_hosts_env = os.getenv("ALLOWED_HOSTS", "")
if allowed_hosts_env:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(",")]
else:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# -----------------
# Apps
# -----------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",

    "myapp",
]

AUTH_USER_MODEL = "myapp.User"

# -----------------
# Middleware (CORS before CommonMiddleware)
# -----------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",            # <- keep high
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -----------------
# CORS (front-end at Vite 5173 for dev, production domain for prod)
# -----------------
cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins_env:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_env.split(",")]
else:
    # Default to development origins
    CORS_ALLOWED_ORIGINS = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["content-type", "authorization"]

# -----------------
# URLs / Templates / WSGI
# -----------------
ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "myapp" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"

# -----------------
# Django login URLs (not critical for JWT, harmless to keep)
# -----------------
LOGIN_URL = "api/login/"
LOGIN_REDIRECT_URL = "api/dashboard/"
LOGOUT_REDIRECT_URL = "api/login/"

# -----------------
# DRF / JWT
# -----------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# -----------------
# DB (Support PostgreSQL in production, SQLite for development)
# -----------------
if os.getenv("DB_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "fitnessdb"),
            "USER": os.getenv("DB_USER", "fitnessuser"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    # Default to SQLite for development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Cache Configuration (Redis in production, LocMem in development)
if os.getenv("USE_REDIS", "False") == "True" and os.getenv("REDIS_HOST"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"redis://{os.getenv('REDIS_HOST', '127.0.0.1')}:{os.getenv('REDIS_PORT', '6379')}/{os.getenv('REDIS_DB', '1')}",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PASSWORD": os.getenv("REDIS_PASSWORD", ""),  # Empty if no password
            },
            "KEY_PREFIX": "fitness_app",
            "TIMEOUT": 300,  # Default timeout 5 minutes
        }
    }
else:
    # Safe default cache (no Redis required in dev)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "local",
        }
    }

# -----------------
# Password validation
# -----------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------
# i18n
# -----------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -----------------
# Static / Media
# -----------------
STATIC_URL = "/myapp/static/"
STATICFILES_DIRS = [BASE_DIR / "myapp" / "static"]
# STATIC_ROOT for production (where collectstatic puts files)
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------
# App-specific constants (if you use them)
# -----------------
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 10
LOGIN_LOCK_MINUTES = 15

MAX_DURATION_DAYS = 365
SIMILARITY_THRESHOLD = 3
TOP_SIMILAR_LIMIT = 3
CLASS_MINUTES_PER_DAY = 24 * 60

WEATHERAPI_API_KEY = os.getenv("WEATHERAPI_API_KEY", "")

# -----------------
# Email Configuration
# -----------------
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For development
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")

# Password reset settings
PASSWORD_RESET_TIMEOUT = 3600  # 1 hour in seconds

# -----------------
# Production Settings (Error Handling, Logging)
# -----------------
if not DEBUG:
    # Security settings for production
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False") == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    
    # Logging configuration
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "file": {
                "level": "ERROR",
                "class": "logging.FileHandler",
                "filename": BASE_DIR / "logs" / "django-errors.log",
                "formatter": "verbose",
            },
            "console": {
                "level": "ERROR",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["file", "console"],
                "level": "ERROR",
                "propagate": True,
            },
        },
    }
    
    # Admin email for error reports
    ADMINS = [
        ("Admin", os.getenv("ADMIN_EMAIL", "admin@example.com")),
    ]