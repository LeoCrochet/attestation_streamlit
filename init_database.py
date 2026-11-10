"""
Скрипт полной инициализации базы данных.
Запуск: python init_database.py
"""
import logging
from database import Database
from db_schema import SCHEMA_QUERIES, MIGRATION_ALTERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_full_db():
    db = Database()
    if not db.connection:
        logger.error("❌ Не удалось подключиться к MySQL. Проверьте .env")
        return

    logger.info("Начинаю создание таблиц...")
    for q in SCHEMA_QUERIES:
        try:
            db.execute_query(q, commit=True)
        except Exception as e:
            logger.error(f"Ошибка создания таблицы: {e}")

    logger.info("Применяю ALTER'ы для старых БД...")
    for q in MIGRATION_ALTERS:
        try:
            # Выполняем без коммита, чтобы избежать блокировок при ошибках
            cursor = db.get_cursor()
            cursor.execute(q)
            db.connection.commit()
        except Exception as e:
            # Игнорируем ошибку дубликата колонки (1060)
            if "1060" not in str(e) and "Duplicate column" not in str(e):
                logger.error(f"Ошибка миграции: {e}")
            pass

    try:
        logger.info("Добавляю пользователей по умолчанию...")
        db.add_default_users()
    except Exception as e:
        logger.error(f"Ошибка добавления пользователей: {e}")

    try:
        logger.info("Добавляю тестовые вопросы...")
        db.add_sample_questions()
    except Exception as e:
        logger.error(f"Ошибка добавления вопросов: {e}")

    logger.info("✅ База данных успешно инициализирована!")


if __name__ == "__main__":
    init_full_db()