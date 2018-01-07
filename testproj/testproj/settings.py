import os

import dj_database_url

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '!z1yj(9uz)zk0gg@5--j)bc4h^i!8))r^dezco8glf190e0&#p'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'test.local',
    '.herokuapp.com',
]
CORS_ORIGIN_ALLOW_ALL = True

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',

    'drf_yasg',
    'snippets',
    'users',
    'articles',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'drf_yasg.middleware.SwaggerExceptionMiddleware',
]

ROOT_URLCONF = 'testproj.urls'

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

WSGI_APPLICATION = 'testproj.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

db_path = os.path.join(BASE_DIR, 'db.sqlite3')
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, default='sqlite:///' + db_path)
}

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

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

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}

SWAGGER_SETTINGS = {
    'LOGIN_URL': '/admin/login',
    'LOGOUT_URL': '/admin/logout',

    'DEFAULT_INFO': 'testproj.urls.swagger_info'
}

if not os.environ.get('DYNO', ''):
    SWAGGER_SETTINGS.update({'VALIDATOR_URL': 'http://localhost:8189'})

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'

TEST_RUNNER = 'testproj.runner.PytestTestRunner'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'pipe_separated': {
            'format': '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        }
    },
    'handlers': {
        'console_log': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'pipe_separated',
        },
    },
    'loggers': {
        'drf_yasg': {
            'handlers': ['console_log'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console_log'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console_log'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.template': {
            'handlers': ['console_log'],
            'level': 'INFO',
            'propagate': False,
        },
        'swagger_spec_validator': {
            'handlers': ['console_log'],
            'level': 'INFO',
            'propagate': False,
        }
    },
    'root': {
        'handlers': ['console_log'],
        'level': 'INFO',
    }
}
