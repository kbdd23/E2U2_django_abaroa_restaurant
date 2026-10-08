import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / 'db.env')


SECRET_KEY = 'django-insecure-+2*ia+#y&5-h$sd4w96jop6%%gxpsrao)-vce&rppuylcv4e)8'

DEBUG = True

ALLOWED_HOSTS = []


INSTALLED_APPS = [
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles', #Tratar de usar comillas dobles para todo lo instalado, para diferenciar dependencias de mongo nativas vs las instaladas
    "django_project.apps.MongoAdminConfig",
    "django_project.apps.MongoAuthConfig",
    "django_project.apps.MongoContentTypesConfig",
    "django_mongodb_backend",
    "home",
    "panel",
    "booking",
    "menu",
    "orders",

]

# Modelo de usuario personalizado: panel.User (migrado desde pages.User del AFM).
# Debe definirse ANTES de la primera migracion de booking/panel, porque
# booking.models.Reserva.cliente y orders.models.Orden.mesero ya lo referencian.
AUTH_USER_MODEL = 'panel.User'

# Sin esto Django usa el default /accounts/login/, que en este proyecto no
# existe: el usuario recibia un 404 en vez del formulario de entrada.

LOGIN_URL = 'login'


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'django_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True, #Deberia ser false, porque queremos que todas nuestras templates que consuman de un solo lugar, no templates autocontenidos. pero se mantiene true.
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'django_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

#Vamos a usar mongo.

DATABASES = {
    'default': {
        'ENGINE': 'django_mongodb_backend',
        'NAME': os.environ.get('MONGODB_DB_NAME', 'django_mongo_db'),
        'HOST': os.environ.get('MONGODB_URI'),
        'OPTIONS': {
            'tls': True,
        },
    }
}

# Router de MongoDB
DATABASE_ROUTERS = ['django_mongodb_backend.routers.MongoRouter']

# Migraciones adaptadas a ObjectId para las apps del framework
MIGRATION_MODULES = {
    'admin': 'mongo_migrations.admin',
    'auth': 'mongo_migrations.auth',
    'contenttypes': 'mongo_migrations.contenttypes',
}


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


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Santiago' #Hora Chilena (para lo de las horas)

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] #Django buscará aquí los archivos del proyecto.

#MongoDB usa ObjectId como primary key en vez de autoincrement
DEFAULT_AUTO_FIELD = 'django_mongodb_backend.fields.ObjectIdAutoField'

"""Para probar la conexión usa: 
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('Servidor:', '.'.join(map(str, connection.get_database_version()))); print('Base:', connection.settings_dict['NAME'])"
"""