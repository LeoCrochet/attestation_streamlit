"""Единая схема БД — используется и init_database.py, и Database.init_db()."""

SCHEMA_QUERIES = [
    # 1. ПОЛЬЗОВАТЕЛИ
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

    # 2. ВОПРОСЫ
    """
    CREATE TABLE IF NOT EXISTS questions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        topic VARCHAR(100) NOT NULL,
        question TEXT NOT NULL,
        options JSON NOT NULL,
        correct_answer INT NOT NULL,
        difficulty INT DEFAULT 1,
        image_path VARCHAR(255) DEFAULT NULL, -- <-- НОВОЕ ПОЛЕ
        created_by VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tags VARCHAR(255) DEFAULT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        explanation TEXT DEFAULT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        updated_by VARCHAR(50) DEFAULT NULL,
        INDEX idx_topic (topic),
        INDEX idx_questions_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 3. ГРУППЫ (с полями заявок)
    """
    CREATE TABLE IF NOT EXISTS `groups` (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) UNIQUE NOT NULL,
        description TEXT,
        curator_id INT DEFAULT NULL,
        start_date DATE DEFAULT NULL,
        end_date DATE DEFAULT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        organization_name VARCHAR(255) DEFAULT NULL,
        organization_address VARCHAR(255) DEFAULT NULL,
        organization_phone VARCHAR(100) DEFAULT NULL,
        organization_email VARCHAR(100) DEFAULT NULL,
        contact_person VARCHAR(150) DEFAULT NULL,
        manager_name VARCHAR(150) DEFAULT NULL,
        created_by VARCHAR(50) DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_groups_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 4. УЧАСТНИКИ ГРУПП
    """
    CREATE TABLE IF NOT EXISTS group_members (
        id INT PRIMARY KEY AUTO_INCREMENT,
        group_id INT NOT NULL,
        user_id INT NOT NULL,
        role_in_group ENUM('student', 'curator', 'assistant') DEFAULT 'student',
        profession VARCHAR(150) DEFAULT NULL,
        education VARCHAR(150) DEFAULT NULL,
        birth_year INT DEFAULT NULL,
        training_type VARCHAR(100) DEFAULT NULL,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        left_at TIMESTAMP NULL DEFAULT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        UNIQUE KEY uq_group_user (group_id, user_id),
        FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 5. ЗАДАНИЯ
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
        is_training BOOLEAN DEFAULT FALSE,
        created_by VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 6. РЕЗУЛЬТАТЫ
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
        INDEX idx_results_assignment (assignment_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 7. ПРОТОКОЛЫ (с file_path и closed_by)
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
        file_path VARCHAR(255) DEFAULT NULL,
        closed_by VARCHAR(50) DEFAULT NULL,
        FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 8. ДОКУМЕНТЫ ГРУППЫ (PDF)
    """
    CREATE TABLE IF NOT EXISTS group_documents (
        id INT PRIMARY KEY AUTO_INCREMENT,
        group_id INT NOT NULL,
        doc_type VARCHAR(50) NOT NULL,
        file_name VARCHAR(255) NOT NULL,
        file_path VARCHAR(255) NOT NULL,
        uploaded_by VARCHAR(50) DEFAULT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE,
        INDEX idx_gd_group (group_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # 9. ЖУРНАЛ ДЕЙСТВИЙ
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

    # 10. ИСТОРИЯ ВОПРОСОВ
    """
    CREATE TABLE IF NOT EXISTS questions_history (
        id INT PRIMARY KEY AUTO_INCREMENT,
        question_id INT NOT NULL,
        action ENUM('create', 'update', 'delete') NOT NULL,
        changed_by VARCHAR(50),
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        old_data JSON,
        new_data JSON
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

MIGRATION_ALTERS = [
    "ALTER TABLE `groups` ADD COLUMN organization_name VARCHAR(255) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN organization_address VARCHAR(255) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN organization_phone VARCHAR(100) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN organization_email VARCHAR(100) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN contact_person VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN manager_name VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN profession VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN education VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN birth_year INT DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN training_type VARCHAR(100) DEFAULT NULL",
    "ALTER TABLE protocols ADD COLUMN file_path VARCHAR(255) DEFAULT NULL",
    "ALTER TABLE protocols ADD COLUMN closed_by VARCHAR(50) DEFAULT NULL",
    "ALTER TABLE assignments ADD COLUMN is_training BOOLEAN DEFAULT FALSE",
    "ALTER TABLE questions ADD COLUMN image_path VARCHAR(255) DEFAULT NULL",
]