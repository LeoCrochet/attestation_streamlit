"""
Модуль работы с базой данных MySQL для системы аттестации.

Содержит класс Database со всеми методами:
- подключение и переподключение
- аутентификация и пользователи
- вопросы (CRUD, массовые операции, фильтры, статистика)
- результаты тестирования
- журнал действий
"""

import hashlib
import json
import logging
import secrets

import mysql.connector
from mysql.connector import Error

from config import get_config

logger = logging.getLogger(__name__)


class Database:
    # ==================================================================
    # ИНИЦИАЛИЗАЦИЯ И ПОДКЛЮЧЕНИЕ
    # ==================================================================

    def __init__(self, config_name='default'):
        self.config = get_config()
        self.connection = None
        ok = self.connect()
        print(f"[Database] __init__ connect() -> {ok}", flush=True)

    def connect(self):
        """Подключение к MySQL."""
        try:
            self.connection = mysql.connector.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE,
                charset='utf8mb4',
                use_pure=True,
                autocommit=False,
            )
            print(
                f"✅ [Database] Подключено: {self.config.MYSQL_USER}@"
                f"{self.config.MYSQL_HOST}:{self.config.MYSQL_PORT}/"
                f"{self.config.MYSQL_DATABASE}",
                flush=True,
            )
            return True
        except Error as e:
            print(f"❌ [Database] MySQL Error: {e}", flush=True)
            self.connection = None
            return False

    def get_cursor(self, dictionary=True):
        """Курсор с авто-переподключением."""
        if not self.connection or not self.connection.is_connected():
            if not self.connect():
                raise RuntimeError(
                    "Нет соединения с MySQL. Проверьте .env, статус mysql, "
                    "наличие БД attestation_db и пользователя attestation_user."
                )
        return self.connection.cursor(dictionary=dictionary)

    def execute_query(self, query, params=None, commit=True):
        """Выполнение запроса."""
        cursor = self.get_cursor()
        try:
            cursor.execute(query, params or ())
            if commit:
                self.connection.commit()
            return cursor
        except Error as e:
            self.connection.rollback()
            logger.error(f"❌ Query Error: {e}")
            raise

    # ==================================================================
    # ПАРОЛИ
    # ==================================================================

    def hash_password(self, password):
        """Хеширование пароля (salt:sha256)."""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256((salt + password).encode())
        return f"{salt}:{hash_obj.hexdigest()}"

    def verify_password(self, stored_hash, password):
        """Проверка пароля."""
        try:
            salt, hash_value = stored_hash.split(':')
            hash_obj = hashlib.sha256((salt + password).encode())
            return hash_obj.hexdigest() == hash_value
        except Exception:
            return False

    # ==================================================================
    # ИНИЦИАЛИЗАЦИЯ СХЕМЫ
    # ==================================================================

    def init_db(self):
        """Инициализация базы данных (создание всех таблиц)."""
        queries = [
            # === ПОЛЬЗОВАТЕЛИ ===
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                role ENUM('user', 'manager', 'methodist', 'admin') DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                department VARCHAR(100),
                position VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                INDEX idx_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === ВОПРОСЫ ===
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INT PRIMARY KEY AUTO_INCREMENT,
                topic VARCHAR(100) NOT NULL,
                question TEXT NOT NULL,
                options JSON NOT NULL,
                correct_answer INT NOT NULL,
                difficulty INT DEFAULT 1,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tags VARCHAR(255) DEFAULT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                explanation TEXT DEFAULT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                updated_by VARCHAR(50) DEFAULT NULL,
                INDEX idx_topic (topic),
                INDEX idx_questions_active (is_active),
                INDEX idx_questions_difficulty (difficulty)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === ГРУППЫ ===
            """
            CREATE TABLE IF NOT EXISTS `groups` (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                curator_id INT DEFAULT NULL,
                start_date DATE DEFAULT NULL,
                end_date DATE DEFAULT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(50) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_groups_active (is_active),
                INDEX idx_groups_curator (curator_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === ЗАДАНИЯ ===
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INT PRIMARY KEY AUTO_INCREMENT,
                group_id INT NOT NULL,
                topic VARCHAR(100) DEFAULT NULL,
                num_questions INT DEFAULT 10,
                max_attempts INT DEFAULT 1,
                time_limit_min INT DEFAULT NULL,
                pass_score INT DEFAULT 60,
                title VARCHAR(255),
                description TEXT,
                due_date TIMESTAMP NULL DEFAULT NULL,
                starts_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('open', 'closed', 'archived') DEFAULT 'open',
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_assignments_group (group_id),
                INDEX idx_assignments_status (status),
                INDEX idx_assignments_due (due_date),
                FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === РЕЗУЛЬТАТЫ ===
            """
            CREATE TABLE IF NOT EXISTS results (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT,
                user_name VARCHAR(50) NOT NULL,
                topic VARCHAR(100),
                score INT DEFAULT 0,
                total_questions INT DEFAULT 0,
                answers JSON,
                time_spent INT,
                group_id INT DEFAULT NULL,
                protocol_id INT DEFAULT NULL,
                assignment_id INT DEFAULT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user (user_id),
                INDEX idx_results_group (group_id),
                INDEX idx_results_assignment (assignment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === ЖУРНАЛ ===
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT,
                action VARCHAR(100) NOT NULL,
                details TEXT,
                ip_address VARCHAR(45),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === ИСТОРИЯ ВОПРОСОВ ===
            """
            CREATE TABLE IF NOT EXISTS questions_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                question_id INT NOT NULL,
                action ENUM('create', 'update', 'delete') NOT NULL,
                changed_by VARCHAR(50),
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                old_data JSON,
                new_data JSON,
                INDEX idx_qh_question (question_id),
                INDEX idx_qh_date (changed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === УЧАСТНИКИ ГРУПП ===
            """
            CREATE TABLE IF NOT EXISTS group_members (
                id INT PRIMARY KEY AUTO_INCREMENT,
                group_id INT NOT NULL,
                user_id INT NOT NULL,
                role_in_group ENUM('student', 'curator', 'assistant') DEFAULT 'student',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP NULL DEFAULT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE KEY uq_group_user (group_id, user_id),
                INDEX idx_gm_group (group_id),
                INDEX idx_gm_user (user_id),
                FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            # === ПРОТОКОЛЫ ===
            """
            CREATE TABLE IF NOT EXISTS protocols (
                id INT PRIMARY KEY AUTO_INCREMENT,
                group_id INT NOT NULL,
                topic VARCHAR(100) DEFAULT NULL,
                title VARCHAR(255) DEFAULT NULL,
                description TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP NULL DEFAULT NULL,
                status ENUM('open', 'closed', 'archived') DEFAULT 'open',
                created_by VARCHAR(50) DEFAULT NULL,
                INDEX idx_protocols_group (group_id),
                FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]

        for query in queries:
            try:
                self.execute_query(query, commit=True)
            except Error as e:
                logger.error(f"❌ Error creating table: {e}")
                print(f"❌ [init_db] {e}", flush=True)

    # ==================================================================
    # ПОЛЬЗОВАТЕЛИ
    # ==================================================================

    def add_default_users(self):
        """Добавление пользователей по умолчанию."""
        users = [
            ('admin', 'admin@system.local', 'admin123',
             'Администратор', 'admin', 'IT', 'Администратор'),
            ('user', 'user@example.com', 'user123',
             'Тестовый пользователь', 'user', 'Разработка', 'Программист'),
        ]

        for user_data in users:
            username, email, password, full_name, role, department, position = user_data
            try:
                cursor = self.get_cursor()
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    continue

                password_hash = self.hash_password(password)
                self.execute_query(
                    """
                    INSERT INTO users
                        (username, email, password_hash, full_name, role,
                         department, position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (username, email, password_hash, full_name, role,
                     department, position),
                    commit=True,
                )
                logger.info(f"✅ User '{username}' created")
            except Error as e:
                logger.error(f"❌ Error creating user '{username}': {e}")

    def get_user_by_username(self, username):
        """Получение пользователя по имени."""
        cursor = self.get_cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND is_active = TRUE",
            (username,),
        )
        return cursor.fetchone()

    def get_user_by_id(self, user_id):
        """Получение пользователя по ID."""
        cursor = self.get_cursor()
        cursor.execute(
            "SELECT * FROM users WHERE id = %s AND is_active = TRUE",
            (user_id,),
        )
        return cursor.fetchone()

    def get_all_users(self, include_inactive=False):
        """Все пользователи (для админки)."""
        cursor = self.get_cursor()
        if include_inactive:
            cursor.execute(
                "SELECT id, username, email, full_name, role, department, "
                "position, is_active, created_at, last_login "
                "FROM users ORDER BY id"
            )
        else:
            cursor.execute(
                "SELECT id, username, email, full_name, role, department, "
                "position, is_active, created_at, last_login "
                "FROM users WHERE is_active = TRUE ORDER BY id"
            )
        return cursor.fetchall()

    def create_user(self, username, password, email=None, full_name=None,
                    role='user', department=None, position=None):
        """Создать пользователя."""
        password_hash = self.hash_password(password)
        self.execute_query(
            """
            INSERT INTO users
                (username, email, password_hash, full_name, role,
                 department, position)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (username, email, password_hash, full_name, role,
             department, position),
            commit=True,
        )
        return self.get_user_by_username(username)

    def update_user(self, user_id, **fields):
        """Обновить поля пользователя."""
        if not fields:
            return False
        fields.pop("id", None)
        fields.pop("created_at", None)
        if "password" in fields:
            fields["password_hash"] = self.hash_password(fields.pop("password"))
        set_sql = ", ".join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [user_id]
        self.execute_query(
            f"UPDATE users SET {set_sql} WHERE id = %s", params, commit=True,
        )
        return True

    def deactivate_user(self, user_id):
        """Деактивировать пользователя."""
        return self.update_user(user_id, is_active=False)

    def authenticate_user(self, username, password):
        """Аутентификация пользователя."""
        user = self.get_user_by_username(username)
        if not user:
            return None

        if self.verify_password(user['password_hash'], password):
            self.execute_query(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                (user['id'],),
                commit=True,
            )
            return user
        return None

    # ==================================================================
    # ВОПРОСЫ
    # ==================================================================

    def add_sample_questions(self):
        """Добавление примеров вопросов."""
        questions = [
            ('Python', 'Что такое PEP 8?',
             json.dumps(['Стандарт оформления кода', 'Версия Python',
                         'Библиотека для PEP', 'Среда разработки']), 0, 1),
            ('Python', 'Какой метод используется для преобразования строки в число?',
             json.dumps(['str()', 'int()', 'float()', 'char()']), 1, 1),
            ('SQL', 'Какой оператор используется для выборки данных?',
             json.dumps(['INSERT', 'SELECT', 'UPDATE', 'DELETE']), 1, 1),
            ('SQL', 'Что такое JOIN?',
             json.dumps(['Объединение таблиц', 'Сортировка',
                         'Группировка', 'Фильтрация']), 0, 2),
            ('Web', 'Что такое HTML?',
             json.dumps(['Язык разметки', 'Язык программирования',
                         'Стиль CSS', 'База данных']), 0, 1),
            ('Web', 'Какой метод HTTP используется для отправки формы?',
             json.dumps(['GET', 'POST', 'PUT', 'DELETE']), 1, 1),
        ]

        try:
            cursor = self.get_cursor()
            cursor.execute("SELECT COUNT(*) as count FROM questions")
            if cursor.fetchone()['count'] > 0:
                return

            for q in questions:
                self.execute_query(
                    """
                    INSERT INTO questions
                        (topic, question, options, correct_answer, difficulty)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    q,
                    commit=True,
                )
            logger.info(f"✅ {len(questions)} sample questions added")
        except Error as e:
            logger.error(f"❌ Error adding sample questions: {e}")

    # ----- Старые методы (совместимость) -----

    def get_topics(self):
        """Список тем (только активные)."""
        cursor = self.get_cursor()
        cursor.execute(
            "SELECT DISTINCT topic FROM questions WHERE is_active = TRUE ORDER BY topic"
        )
        return [row['topic'] for row in cursor.fetchall()]

    def get_questions_by_topic(self, topic=None):
        """Вопросы по теме (только активные)."""
        cursor = self.get_cursor()
        if topic and topic != 'all':
            cursor.execute(
                "SELECT * FROM questions WHERE topic = %s AND is_active = TRUE",
                (topic,),
            )
        else:
            cursor.execute("SELECT * FROM questions WHERE is_active = TRUE")
        return cursor.fetchall()

    # ----- Расширенные методы -----

    def get_all_topics(self, include_archived=False):
        """Все темы (включая архив при include_archived=True)."""
        cursor = self.get_cursor()
        if include_archived:
            cursor.execute("SELECT DISTINCT topic FROM questions ORDER BY topic")
        else:
            cursor.execute(
                "SELECT DISTINCT topic FROM questions WHERE is_active = TRUE ORDER BY topic"
            )
        return [row['topic'] for row in cursor.fetchall()]

    def get_all_tags(self):
        """Все уникальные теги."""
        cursor = self.get_cursor()
        cursor.execute(
            "SELECT tags FROM questions WHERE tags IS NOT NULL AND tags != ''"
        )
        tags = set()
        for row in cursor.fetchall():
            for t in (row['tags'] or '').split(','):
                t = t.strip()
                if t:
                    tags.add(t)
        return sorted(tags)

    def get_question_by_id(self, question_id):
        """Один вопрос по ID."""
        cursor = self.get_cursor()
        cursor.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
        return cursor.fetchone()

    def get_questions_paginated(self, topic=None, search=None, difficulty=None,
                                is_active=None, limit=50, offset=0):
        """
        Вопросы с фильтрами и пагинацией.
        Возвращает (rows, total_count).
        """
        where = ["1=1"]
        params = []

        if topic and topic != "Все":
            where.append("topic = %s")
            params.append(topic)

        if search:
            where.append("(question LIKE %s OR tags LIKE %s)")
            like = f"%{search}%"
            params.extend([like, like])

        if difficulty:
            where.append("difficulty = %s")
            params.append(difficulty)

        if is_active is not None:
            where.append("is_active = %s")
            params.append(bool(is_active))

        where_sql = " AND ".join(where)
        cursor = self.get_cursor()

        cursor.execute(
            f"SELECT COUNT(*) AS cnt FROM questions WHERE {where_sql}", params
        )
        total = cursor.fetchone()["cnt"]

        cursor.execute(
            f"""
            SELECT * FROM questions
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        return cursor.fetchall(), total

    def add_question(self, topic, question, options, correct_answer,
                     difficulty=1, created_by=None, tags=None, explanation=None):
        """Добавить вопрос. Возвращает id."""
        cursor = self.get_cursor()
        self.execute_query(
            """
            INSERT INTO questions
                (topic, question, options, correct_answer, difficulty,
                 created_by, tags, explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (topic, question, json.dumps(options, ensure_ascii=False),
             correct_answer, difficulty, created_by, tags, explanation),
            commit=True,
        )
        new_id = cursor.lastrowid

        try:
            self.execute_query(
                """
                INSERT INTO questions_history
                    (question_id, action, changed_by, new_data)
                VALUES (%s, 'create', %s, %s)
                """,
                (new_id, created_by, json.dumps({
                    "topic": topic, "question": question,
                    "options": options, "correct_answer": correct_answer,
                }, ensure_ascii=False)),
                commit=True,
            )
        except Exception:
            pass  # история — не критично

        return new_id

    def update_question(self, question_id, **fields):
        """Обновить поля вопроса."""
        if not fields:
            return False

        fields.pop("id", None)
        fields.pop("created_at", None)

        old = self.get_question_by_id(question_id)
        if not old:
            return False

        if "options" in fields and not isinstance(fields["options"], str):
            fields["options"] = json.dumps(fields["options"], ensure_ascii=False)

        set_sql = ", ".join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [question_id]

        self.execute_query(
            f"UPDATE questions SET {set_sql} WHERE id = %s", params, commit=True,
        )

        try:
            self.execute_query(
                """
                INSERT INTO questions_history
                    (question_id, action, changed_by, old_data, new_data)
                VALUES (%s, 'update', %s, %s, %s)
                """,
                (
                    question_id,
                    fields.get("updated_by"),
                    json.dumps(old, ensure_ascii=False, default=str),
                    json.dumps(fields, ensure_ascii=False, default=str),
                ),
                commit=True,
            )
        except Exception:
            pass

        return True

    def delete_question(self, question_id, deleted_by=None):
        """Мягкое удаление (is_active=FALSE)."""
        return self.update_question(
            question_id, is_active=False, updated_by=deleted_by,
        )

    def hard_delete_question(self, question_id, deleted_by=None):
        """Полное удаление записи."""
        old = self.get_question_by_id(question_id)
        if not old:
            return False

        self.execute_query(
            "DELETE FROM questions WHERE id = %s", (question_id,), commit=True,
        )

        try:
            self.execute_query(
                """
                INSERT INTO questions_history
                    (question_id, action, changed_by, old_data)
                VALUES (%s, 'delete', %s, %s)
                """,
                (question_id, deleted_by,
                 json.dumps(old, ensure_ascii=False, default=str)),
                commit=True,
            )
        except Exception:
            pass

        return True

    def bulk_add_questions(self, questions, created_by=None):
        """
        Массовое добавление.
        questions: список dict {topic, question, options, correct_answer,
                                difficulty, tags, explanation}
        Возвращает (added_count, errors).
        """
        added = 0
        errors = []
        for i, q in enumerate(questions, start=1):
            try:
                self.add_question(
                    topic=q["topic"],
                    question=q["question"],
                    options=q["options"],
                    correct_answer=q["correct_answer"],
                    difficulty=q.get("difficulty", 1),
                    created_by=created_by,
                    tags=q.get("tags"),
                    explanation=q.get("explanation"),
                )
                added += 1
            except Exception as e:
                errors.append(f"Строка {i}: {e}")
        return added, errors

    def bulk_delete_questions(self, question_ids, deleted_by=None):
        """Мягко удалить список вопросов."""
        if not question_ids:
            return 0
        ids_str = ",".join(["%s"] * len(question_ids))
        self.execute_query(
            f"UPDATE questions SET is_active = FALSE, updated_by = %s "
            f"WHERE id IN ({ids_str})",
            [deleted_by] + list(question_ids),
            commit=True,
        )
        return len(question_ids)

    def bulk_update_topic(self, question_ids, new_topic, updated_by=None):
        """Переместить вопросы в другую тему."""
        if not question_ids:
            return 0
        ids_str = ",".join(["%s"] * len(question_ids))
        self.execute_query(
            f"UPDATE questions SET topic = %s, updated_by = %s "
            f"WHERE id IN ({ids_str})",
            [new_topic, updated_by] + list(question_ids),
            commit=True,
        )
        return len(question_ids)

    def bulk_update_difficulty(self, question_ids, new_difficulty, updated_by=None):
        """Изменить сложность группы вопросов."""
        if not question_ids:
            return 0
        ids_str = ",".join(["%s"] * len(question_ids))
        self.execute_query(
            f"UPDATE questions SET difficulty = %s, updated_by = %s "
            f"WHERE id IN ({ids_str})",
            [new_difficulty, updated_by] + list(question_ids),
            commit=True,
        )
        return len(question_ids)

    def get_questions_stats(self):
        """Статистика по банку вопросов."""
        cursor = self.get_cursor()

        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(is_active = TRUE) AS active,
                SUM(is_active = FALSE) AS archived,
                COUNT(DISTINCT topic) AS topics,
                AVG(difficulty) AS avg_difficulty
            FROM questions
        """)
        overall = cursor.fetchone()

        cursor.execute("""
            SELECT topic, COUNT(*) AS cnt,
                   AVG(difficulty) AS avg_diff,
                   SUM(is_active = FALSE) AS archived
            FROM questions
            GROUP BY topic
            ORDER BY cnt DESC
        """)
        by_topic = cursor.fetchall()

        cursor.execute("""
            SELECT difficulty, COUNT(*) AS cnt
            FROM questions
            WHERE is_active = TRUE
            GROUP BY difficulty
            ORDER BY difficulty
        """)
        by_difficulty = cursor.fetchall()

        return {
            "overall": overall,
            "by_topic": by_topic,
            "by_difficulty": by_difficulty,
        }

    def get_questions_history(self, question_id=None, limit=100):
        """История изменений вопросов."""
        cursor = self.get_cursor()
        if question_id:
            cursor.execute(
                """
                SELECT * FROM questions_history
                WHERE question_id = %s
                ORDER BY changed_at DESC LIMIT %s
                """,
                (question_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM questions_history
                ORDER BY changed_at DESC LIMIT %s
                """,
                (limit,),
            )
        return cursor.fetchall()

    # ==================================================================
    # РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ
    # ==================================================================

    def save_result(self, user_id, user_name, topic, answers, score, total,
                    time_spent=None, group_id=None, protocol_id=None,
                    assignment_id=None):
        """Сохранение результатов теста."""
        cursor = self.get_cursor()
        self.execute_query(
            """
            INSERT INTO results
            (user_id, user_name, topic, score, total_questions,
             answers, time_spent, group_id, protocol_id, assignment_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, user_name, topic, score, total,
             json.dumps(answers, ensure_ascii=False), time_spent,
             group_id, protocol_id, assignment_id),
            commit=True,
        )
        return cursor.lastrowid

    def get_results(self, user_id=None, limit=None):
        """Получение результатов."""
        cursor = self.get_cursor()
        query = "SELECT * FROM results"
        params = []

        if user_id:
            query += " WHERE user_id = %s"
            params.append(user_id)

        query += " ORDER BY date DESC"

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        cursor.execute(query, params)
        return cursor.fetchall()

    def get_user_statistics(self, user_id):
        """Статистика пользователя."""
        cursor = self.get_cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_tests,
                AVG(score * 100.0 / total_questions) as avg_score,
                MAX(score * 100.0 / total_questions) as max_score,
                SUM(score) as total_correct,
                SUM(total_questions) as total_questions
            FROM results
            WHERE user_id = %s
        """, (user_id,))
        overall = cursor.fetchone()

        cursor.execute("""
            SELECT
                topic,
                COUNT(*) as tests_count,
                AVG(score * 100.0 / total_questions) as avg_score
            FROM results
            WHERE user_id = %s
            GROUP BY topic
            ORDER BY avg_score DESC
        """, (user_id,))
        by_topic = cursor.fetchall()

        return {
            'overall': overall,
            'by_topic': by_topic,
        }

        # ==================================================================
        # ЗАДАНИЯ
        # ==================================================================

    def create_assignment(self, group_id, topic=None, num_questions=10,
                          max_attempts=1, time_limit_min=None, pass_score=60,
                          title=None, description=None, due_date=None,
                          created_by=None):
        cursor = self.get_cursor()
        self.execute_query("""
                           INSERT INTO assignments
                           (group_id, topic, num_questions, max_attempts,
                            time_limit_min, pass_score, title, description,
                            due_date, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           """, (group_id, topic, num_questions, max_attempts,
                                 time_limit_min, pass_score, title, description,
                                 due_date, created_by), commit=True)
        return cursor.lastrowid

    def get_assignment(self, assignment_id):
        cursor = self.get_cursor()
        cursor.execute("""
                       SELECT a.*, g.name AS group_name
                       FROM assignments a
                                JOIN `groups` g ON g.id = a.group_id
                       WHERE a.id = %s
                       """, (assignment_id,))
        return cursor.fetchone()

    def get_all_assignments(self, status=None):
        cursor = self.get_cursor()
        where = ""
        params = []
        if status:
            where = "WHERE a.status = %s"
            params.append(status)

        cursor.execute(f"""
               SELECT a.*,
                      g.name AS group_name,
                      (SELECT COUNT(*) FROM group_members gm
                       WHERE gm.group_id = a.group_id AND gm.is_active = TRUE) AS total_students,
                      (SELECT COUNT(DISTINCT r.user_id) FROM results r
                       WHERE r.assignment_id = a.id) AS completed_count
               FROM assignments a
               JOIN `groups` g ON g.id = a.group_id
               {where}
               ORDER BY a.status, a.created_at DESC
           """, params)
        return cursor.fetchall()

    def update_assignment(self, assignment_id, **fields):
        if not fields:
            return False
        fields.pop("id", None)
        fields.pop("created_at", None)
        set_sql = ", ".join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [assignment_id]
        self.execute_query(f"UPDATE assignments SET {set_sql} WHERE id = %s",
                           params, commit=True)
        return True

    def close_assignment(self, assignment_id):
        return self.update_assignment(assignment_id, status="closed")

    def archive_assignment(self, assignment_id):
        return self.update_assignment(assignment_id, status="archived")

    def get_user_assignments(self, user_id, only_active=True):
        cursor = self.get_cursor()
        status_filter = "AND a.status = 'open'" if only_active else ""

        cursor.execute(f"""
               SELECT
                   a.*,
                   g.name AS group_name,
                   (SELECT COUNT(*) FROM results r
                    WHERE r.assignment_id = a.id AND r.user_id = %s) AS attempts_used,
                   (SELECT MAX(r.score * 100.0 / NULLIF(r.total_questions, 0))
                    FROM results r
                    WHERE r.assignment_id = a.id AND r.user_id = %s) AS best_score
               FROM group_members gm
               JOIN assignments a ON a.group_id = gm.group_id
               JOIN `groups` g ON g.id = a.group_id
               WHERE gm.user_id = %s AND gm.is_active = TRUE
               {status_filter}
               ORDER BY a.due_date IS NULL, a.due_date, a.created_at DESC
           """, (user_id, user_id, user_id))
        return cursor.fetchall()

    def get_assignment_statistics(self, assignment_id):
        cursor = self.get_cursor()

        cursor.execute("""
                       SELECT a.group_id,
                              (SELECT COUNT(*)
                               FROM group_members gm
                               WHERE gm.group_id = a.group_id
                                 AND gm.is_active = TRUE) AS total_students
                       FROM assignments a
                       WHERE a.id = %s
                       """, (assignment_id,))
        info = cursor.fetchone()

        cursor.execute("""
                       SELECT u.id                                                AS user_id,
                              u.username,
                              u.full_name,
                              COUNT(r.id)                                         AS attempts,
                              MAX(r.score * 100.0 / NULLIF(r.total_questions, 0)) AS best_score,
                              MAX(r.date)                                         AS last_attempt
                       FROM group_members gm
                                JOIN users u ON u.id = gm.user_id
                                LEFT JOIN results r ON r.user_id = u.id AND r.assignment_id = %s
                       WHERE gm.group_id = (SELECT group_id FROM assignments WHERE id = %s)
                         AND gm.is_active = TRUE
                       GROUP BY u.id, u.username, u.full_name
                       ORDER BY u.full_name
                       """, (assignment_id, assignment_id))
        students = cursor.fetchall()

        return {"info": info, "students": students}

    # ==================================================================
    # ЖУРНАЛ ДЕЙСТВИЙ
    # ==================================================================

    def log_action(self, user_id, action, details=None, ip_address=None):
        """Логирование действий."""
        try:
            self.execute_query(
                """
                INSERT INTO audit_log (user_id, action, details, ip_address)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, action, details, ip_address),
                commit=True,
            )
        except Exception as e:
            logger.error(f"❌ log_action failed: {e}")

    def get_audit_log(self, limit=100):
        """Журнал действий."""
        cursor = self.get_cursor()
        cursor.execute(
            """
            SELECT * FROM audit_log
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cursor.fetchall()

        # ==================================================================
        # ГРУППЫ ОБУЧЕНИЯ
        # ==================================================================

    def get_all_groups(self, only_active=False, include_member_count=True):
        """Список групп."""
        cursor = self.get_cursor()
        where = "WHERE g.is_active = TRUE" if only_active else ""
        query = f"""
            SELECT g.*,
                   u.full_name AS curator_name,
                   u.username  AS curator_username,
                   (SELECT COUNT(*) FROM group_members gm
                    WHERE gm.group_id = g.id AND gm.is_active = TRUE) AS member_count
            FROM `groups` g
            LEFT JOIN users u ON u.id = g.curator_id
            {where}
            ORDER BY g.is_active DESC, g.name
        """
        cursor.execute(query)
        return cursor.fetchall()

    def get_group_by_id(self, group_id):
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT g.*, u.full_name AS curator_name
            FROM `groups` g
            LEFT JOIN users u ON u.id = g.curator_id
            WHERE g.id = %s
        """, (group_id,))
        return cursor.fetchone()

    def create_group(self, name, description=None, curator_id=None,
                     start_date=None, end_date=None, created_by=None):
        cursor = self.get_cursor()
        self.execute_query("""
            INSERT INTO `groups` (name, description, curator_id,
                                  start_date, end_date, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, description, curator_id, start_date, end_date, created_by),
            commit=True)
        return cursor.lastrowid

    def update_group(self, group_id, **fields):
        if not fields:
            return False
        fields.pop("id", None)
        fields.pop("created_at", None)
        set_sql = ", ".join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [group_id]
        self.execute_query(f"UPDATE `groups` SET {set_sql} WHERE id = %s",
                           params, commit=True)
        return True

    def deactivate_group(self, group_id):
        return self.update_group(group_id, is_active=False)

    def add_group_member(self, group_id, user_id, role_in_group="student"):
        """Добавить участника (или реактивировать)."""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT id, is_active FROM group_members
            WHERE group_id = %s AND user_id = %s
        """, (group_id, user_id))
        existing = cursor.fetchone()

        if existing:
            self.execute_query("""
                UPDATE group_members
                SET is_active = TRUE, left_at = NULL, role_in_group = %s
                WHERE id = %s
            """, (role_in_group, existing["id"]), commit=True)
            return existing["id"]

        self.execute_query("""
            INSERT INTO group_members (group_id, user_id, role_in_group)
            VALUES (%s, %s, %s)
        """, (group_id, user_id, role_in_group), commit=True)
        return cursor.lastrowid

    def remove_group_member(self, group_id, user_id):
        self.execute_query("""
            UPDATE group_members
            SET is_active = FALSE, left_at = CURRENT_TIMESTAMP
            WHERE group_id = %s AND user_id = %s
        """, (group_id, user_id), commit=True)
        return True

    def get_group_members(self, group_id, only_active=True):
        cursor = self.get_cursor()
        where = "AND gm.is_active = TRUE" if only_active else ""
        cursor.execute(f"""
            SELECT gm.*, u.username, u.full_name, u.email, u.role
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = %s {where}
            ORDER BY u.full_name, u.username
        """, (group_id,))
        return cursor.fetchall()

    def get_user_groups(self, user_id, only_active=True):
        cursor = self.get_cursor()
        where = "AND gm.is_active = TRUE" if only_active else ""
        cursor.execute(f"""
            SELECT g.*, gm.role_in_group, gm.joined_at
            FROM group_members gm
            JOIN `groups` g ON g.id = gm.group_id
            WHERE gm.user_id = %s {where}
            ORDER BY g.name
        """, (user_id,))
        return cursor.fetchall()

    def get_group_statistics(self, group_id, topic=None):
        cursor = self.get_cursor()
        where_topic = "AND r.topic = %s" if topic else ""
        params = [group_id]
        if topic:
            params.append(topic)

        cursor.execute(f"""
            SELECT
                u.id             AS user_id,
                u.username,
                u.full_name,
                COUNT(r.id)      AS tests_count,
                AVG(r.score * 100.0 / NULLIF(r.total_questions, 0)) AS avg_score,
                MAX(r.score * 100.0 / NULLIF(r.total_questions, 0)) AS max_score,
                MAX(r.date)      AS last_test_date,
                SUM(r.score)     AS total_correct,
                SUM(r.total_questions) AS total_questions
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            LEFT JOIN results r ON r.user_id = u.id
                AND (r.group_id = gm.group_id OR r.group_id IS NULL)
                {where_topic}
            WHERE gm.group_id = %s AND gm.is_active = TRUE
            GROUP BY u.id, u.username, u.full_name
            ORDER BY u.full_name, u.username
        """, params)
        return cursor.fetchall()

    def get_group_results_detailed(self, group_id, topic=None,
                                   date_from=None, date_to=None):
        cursor = self.get_cursor()
        where = ["gm.group_id = %s", "gm.is_active = TRUE"]
        params = [group_id]

        if topic:
            where.append("r.topic = %s")
            params.append(topic)
        if date_from:
            where.append("r.date >= %s")
            params.append(date_from)
        if date_to:
            where.append("r.date <= %s")
            params.append(date_to)

        where_sql = " AND ".join(where)

        cursor.execute(f"""
            SELECT
                r.id, r.date, r.topic, r.score, r.total_questions,
                r.time_spent, r.group_id,
                (r.score * 100.0 / NULLIF(r.total_questions, 0)) AS percentage,
                u.id AS user_id, u.username, u.full_name
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            JOIN results r ON r.user_id = u.id
            WHERE {where_sql}
            ORDER BY u.full_name, r.date DESC
        """, params)
        return cursor.fetchall()

        # ==================================================================
        # ПРОТОКОЛЫ
        # ==================================================================

    def create_protocol(self, group_id, topic, title=None, description=None,
                        created_by=None):
        cursor = self.get_cursor()
        self.execute_query("""
                           INSERT INTO protocols (group_id, topic, title, description, created_by)
                           VALUES (%s, %s, %s, %s, %s)
                           """, (group_id, topic, title, description, created_by), commit=True)
        return cursor.lastrowid

    def get_protocol(self, protocol_id):
        cursor = self.get_cursor()
        cursor.execute("""
                       SELECT p.*, g.name AS group_name
                       FROM protocols p
                                JOIN groups g ON g.id = p.group_id
                       WHERE p.id = %s
                       """, (protocol_id,))
        return cursor.fetchone()

    def get_protocols_for_group(self, group_id):
        cursor = self.get_cursor()
        cursor.execute("""
                       SELECT *
                       FROM protocols
                       WHERE group_id = %s
                       ORDER BY started_at DESC
                       """, (group_id,))
        return cursor.fetchall()

    def close_protocol(self, protocol_id):
        self.execute_query("""
                           UPDATE protocols
                           SET status    = 'closed',
                               closed_at = CURRENT_TIMESTAMP
                           WHERE id = %s
                           """, (protocol_id,), commit=True)
        return True