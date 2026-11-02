
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


# --------------------------------------------------
# BASE DIRECTORY AND ENVIRONMENT
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------
# SECURITY SETTINGS
# --------------------------------------------------

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be configured."
    )

DEBUG = os.getenv(
    "DJANGO_DEBUG",
    "False" if os.getenv("RENDER") else "True"
).lower() == "true"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)

extra_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS.extend(
    host.strip()
    for host in extra_hosts.split(",")
    if host.strip()
)


# --------------------------------------------------
# APPLICATIONS
# --------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "store",
]


# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# --------------------------------------------------
# URL AND TEMPLATE CONFIGURATION
# --------------------------------------------------

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"


# --------------------------------------------------
# DATABASE CONFIGURATION (Multi-Engine: PostgreSQL, TiDB & MySQL)
# --------------------------------------------------

import ssl
import dj_database_url


def verify_ssl_ca_bundle(ca_path: str) -> str:
    """Validate that ca_path exists and is a readable, valid X.509 CA certificate bundle.

    Raises django.core.exceptions.ImproperlyConfigured if the file is missing,
    corrupted, or contains no loadable CA certificates.
    """
    if not ca_path or not os.path.exists(ca_path):
        raise ImproperlyConfigured(
            f"TiDB Cloud SSL CA bundle was not found at '{ca_path}'."
        )
    try:
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=ca_path)
        certs = ctx.get_ca_certs()
        if not certs:
            raise ValueError("No valid X.509 certificates found in bundle.")
    except Exception as exc:
        raise ImproperlyConfigured(
            f"TiDB Cloud SSL CA bundle at '{ca_path}' is invalid and cannot be loaded for TLS verification: {exc}"
        ) from exc
    return ca_path


database_url = os.getenv("DATABASE_URL", "").strip()
db_engine_env = os.getenv("DB_ENGINE", "").strip().lower()

if database_url:
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        DATABASES = {
            "default": dj_database_url.config(
                default=database_url,
                conn_max_age=600,
                conn_health_checks=True,
                ssl_require=True,
            )
        }
    else:
        # MySQL / TiDB via DATABASE_URL
        db_config = dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
        host = (db_config.get("HOST") or "").lower()
        target_tidb_host = (os.getenv("TIDB_HOST") or os.getenv("DB_HOST", "")).strip().lower()
        is_tidb_url = (
            "tidbcloud.com" in host
            or (bool(target_tidb_host) and host == target_tidb_host and target_tidb_host not in ("127.0.0.1", "localhost"))
        )

        if is_tidb_url:
            db_config["ENGINE"] = "common.db_backends.tidb"
            if not db_config.get("PORT"):
                db_config["PORT"] = 4000
            options = {
                "charset": "utf8mb4",
                "use_pure": True,
                "connection_timeout": 15,
                "raise_on_warnings": False,
            }
            explicit_ca = os.getenv("DB_SSL_CA", "").strip() or os.getenv("TIDB_SSL_CA", "").strip()
            if explicit_ca:
                ca_path = verify_ssl_ca_bundle(explicit_ca)
            else:
                auto_candidates = [
                    str(BASE_DIR / "certs" / "isrgrootx1.pem"),
                    str(BASE_DIR / "backend" / "certs" / "isrgrootx1.pem"),
                    "/etc/ssl/certs/ca-certificates.crt",
                    "/etc/pki/tls/certs/ca-bundle.crt",
                ]
                ca_path = ""
                for candidate in auto_candidates:
                    if candidate and os.path.exists(candidate):
                        try:
                            ca_path = verify_ssl_ca_bundle(candidate)
                            break
                        except ImproperlyConfigured:
                            continue
                if not ca_path:
                    raise ImproperlyConfigured(
                        "TiDB Cloud requires a valid SSL CA certificate bundle (e.g. ISRG Root X1) "
                        "for strict TLS verification. None was found in certs/isrgrootx1.pem or system trust stores."
                    )
            options["ssl_ca"] = ca_path
            options["ssl_verify_cert"] = True
            options["ssl_verify_identity"] = True

            conn_max_age_val = os.getenv("DB_CONN_MAX_AGE", "0").strip()
            try:
                db_config["CONN_MAX_AGE"] = int(conn_max_age_val)
            except ValueError:
                db_config["CONN_MAX_AGE"] = 0
            db_config["CONN_HEALTH_CHECKS"] = db_config["CONN_MAX_AGE"] > 0
            db_config["OPTIONS"] = options
            DATABASES = {"default": db_config}
        else:
            options = db_config.get("OPTIONS", {})
            ssl_val = options.pop("ssl-mode", None) or options.pop("sslmode", None)
            options.pop("ssl_require", None)

            if host and host not in ("127.0.0.1", "localhost"):
                options["ssl_mode"] = "REQUIRED" if not ssl_val or "require" in str(ssl_val).lower() else str(ssl_val)

                ca_path = os.getenv("DB_SSL_CA", "").strip()
                if not ca_path:
                    for candidate in [BASE_DIR / "backend" / "aiven-ca.pem", BASE_DIR / "aiven-ca.pem"]:
                        if candidate.exists():
                            ca_path = str(candidate)
                            break
                if ca_path and os.path.exists(ca_path):
                    options["ssl"] = {"ca": ca_path}

            options.setdefault("charset", "utf8mb4")
            db_config["OPTIONS"] = options
            DATABASES = {"default": db_config}
else:
    db_engine = db_engine_env
    db_port = os.getenv("DB_PORT", "").strip()
    db_host = os.getenv("DB_HOST", "").strip()

    is_postgres = (
        "postgres" in db_engine
        or db_port == "5432"
        or ".neon.tech" in db_host.lower()
    )

    is_tidb = (
        db_engine in ("tidb", "tidbcloud")
        or "tidbcloud.com" in db_host.lower()
        or bool(os.getenv("TIDB_HOST", "").strip())
    )

    if is_postgres:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("DB_NAME", "neondb"),
                "USER": os.getenv("DB_USER", ""),
                "PASSWORD": os.getenv("DB_PASSWORD", ""),
                "HOST": os.getenv("DB_HOST", ""),
                "PORT": os.getenv("DB_PORT", "5432"),
                "OPTIONS": {
                    "sslmode": os.getenv("DB_SSLMODE", "require"),
                },
                "CONN_MAX_AGE": 600,
                "CONN_HEALTH_CHECKS": True,
            }
        }
    elif is_tidb:
        tidb_port_raw = os.getenv("TIDB_PORT") or os.getenv("DB_PORT") or "4000"
        if str(tidb_port_raw).strip() == "3306" and not os.getenv("TIDB_PORT"):
            tidb_port_raw = "4000"
        try:
            tidb_port = int(str(tidb_port_raw).strip())
        except (ValueError, TypeError):
            tidb_port = 4000

        explicit_ca = os.getenv("DB_SSL_CA", "").strip() or os.getenv("TIDB_SSL_CA", "").strip()
        if explicit_ca:
            ca_path = verify_ssl_ca_bundle(explicit_ca)
        else:
            auto_candidates = [
                str(BASE_DIR / "certs" / "isrgrootx1.pem"),
                str(BASE_DIR / "backend" / "certs" / "isrgrootx1.pem"),
                "/etc/ssl/certs/ca-certificates.crt",
                "/etc/pki/tls/certs/ca-bundle.crt",
            ]
            ca_path = ""
            for candidate in auto_candidates:
                if candidate and os.path.exists(candidate):
                    try:
                        ca_path = verify_ssl_ca_bundle(candidate)
                        break
                    except ImproperlyConfigured:
                        continue
            if not ca_path:
                raise ImproperlyConfigured(
                    "TiDB Cloud requires a valid SSL CA certificate bundle (e.g. ISRG Root X1) "
                    "for strict TLS verification. None was found in certs/isrgrootx1.pem or system trust stores."
                )

        tidb_options = {
            "charset": "utf8mb4",
            "use_pure": True,
            "connection_timeout": 15,
            "raise_on_warnings": False,
            "ssl_ca": ca_path,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }

        conn_max_age_val = os.getenv("DB_CONN_MAX_AGE", "0").strip()
        try:
            conn_max_age = int(conn_max_age_val)
        except ValueError:
            conn_max_age = 0

        DATABASES = {
            "default": {
                "ENGINE": "common.db_backends.tidb",
                "NAME": os.getenv("DB_NAME") or os.getenv("TIDB_NAME") or os.getenv("TIDB_DATABASE") or "fashion_store",
                "USER": os.getenv("DB_USER") or os.getenv("TIDB_USER", ""),
                "PASSWORD": os.getenv("DB_PASSWORD") or os.getenv("TIDB_PASSWORD", ""),
                "HOST": os.getenv("DB_HOST") or os.getenv("TIDB_HOST", ""),
                "PORT": tidb_port,
                "OPTIONS": tidb_options,
                "CONN_MAX_AGE": conn_max_age,
                "CONN_HEALTH_CHECKS": conn_max_age > 0,
            }
        }
    else:
        # Default to MySQL (e.g. Aiven cloud MySQL or local development on 127.0.0.1:3306)
        db_options = {
            "charset": "utf8mb4",
        }

        # If connecting to a remote cloud MySQL host (e.g. Aiven), enforce SSL REQUIRED
        is_remote_mysql = bool(db_host and db_host.lower() not in ("127.0.0.1", "localhost"))
        if is_remote_mysql:
            db_options["ssl_mode"] = os.getenv("DB_SSLMODE", "REQUIRED")

            ca_path = os.getenv("DB_SSL_CA", "").strip()
            if not ca_path:
                for candidate in [BASE_DIR / "backend" / "aiven-ca.pem", BASE_DIR / "aiven-ca.pem"]:
                    if candidate.exists():
                        ca_path = str(candidate)
                        break
            if ca_path and os.path.exists(ca_path):
                db_options["ssl"] = {"ca": ca_path}

        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": os.getenv("DB_NAME", "fashion_store"),
                "USER": os.getenv("DB_USER", "root"),
                "PASSWORD": os.getenv("DB_PASSWORD", ""),
                "HOST": os.getenv("DB_HOST", "127.0.0.1"),
                "PORT": os.getenv("DB_PORT", "3306"),
                "OPTIONS": db_options,
                "CONN_MAX_AGE": 600 if is_remote_mysql else 0,
                "CONN_HEALTH_CHECKS": True if is_remote_mysql else False,
            }
        }


# --------------------------------------------------
# PASSWORD VALIDATION
# --------------------------------------------------

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


# --------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------
# STATIC FILES - WHITENOISE
# --------------------------------------------------

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# --------------------------------------------------
# CORS - REACT FRONTEND
# --------------------------------------------------

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "https://veloura-fashion-ten.vercel.app" if not DEBUG else ""
).strip().rstrip("/")

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://veloura-fashion.vercel.app",
    "https://veloura-fashion-ten.vercel.app",
]

if FRONTEND_URL and FRONTEND_URL not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(FRONTEND_URL)

# Allow any localhost or 127.0.0.1 port pattern dynamically, and Vercel domains
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$",
    r"^https://.*\.vercel\.app$",
]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://veloura-fashion.vercel.app",
    "https://veloura-fashion-ten.vercel.app",
]

if FRONTEND_URL and FRONTEND_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(FRONTEND_URL)


# --------------------------------------------------
# PRODUCTION SECURITY
# --------------------------------------------------

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = not DEBUG

SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_SECURE = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True


# --------------------------------------------------
# EMAIL
# --------------------------------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Veloura Fashion <noreply@veloura.example>")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")

if EMAIL_HOST and EMAIL_HOST_USER:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# --------------------------------------------------
# REST FRAMEWORK & SIMPLE JWT
# --------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "store": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
