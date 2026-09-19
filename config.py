import os
from dotenv import load_dotenv
# Абсолютный путь к .env рядом с config.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))
import logging

load_dotenv()


class Config:
    """Конфигурация приложения"""

    # Секретный ключ
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Настройки MySQL
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3306)
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'attestation_user'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'Secure_Password_123!'
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'attestation_db'

    # Настройки приложения
    APP_NAME = 'Система аттестации'
    APP_VERSION = '1.0.0'

    # Настройки тестирования
    QUESTIONS_PER_TEST = 10
    MAX_QUESTIONS_PER_TEST = 30
    MIN_QUESTIONS_PER_TEST = 5

    # Безопасность
    PASSWORD_MIN_LENGTH = 6

    # Настройки логирования
    LOG_FILE = '/var/log/attestation_streamlit/app.log'
    LOG_LEVEL = logging.INFO


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    env = os.environ.get('FLASK_ENV', 'production')
    return config.get(env, config['default'])