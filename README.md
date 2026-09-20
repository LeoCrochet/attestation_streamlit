# 🎓 Система аттестации

Веб-приложение для проведения аттестации и обучения: тестирование сотрудников
и студентов, управление вопросами, группами обучения, отчёты и протоколы.

**Стек:** Python 3.11+ · Streamlit · MySQL 8 · Nginx · systemd · Ubuntu 24.04+

---

## ✨ Возможности

### 🔐 Аутентификация и роли

| Роль | Что доступно |
|---|---|
| **`user`** | Тестирование, свои результаты, профиль |
| **`manager`** | То же, что `user` (расширения в разработке) |
| **`methodist`** | Всё выше **+ 👨‍🏫 Кабинет методиста + 👥 Группы** |
| **`admin`** | Всё выше **+ ⚙️ Администрирование пользователей** |

### 📝 Тестирование
- Прохождение теста по выбранной теме
- Настройка количества вопросов
- Подсчёт результата, отображение детальных ответов
- Шарики при успешном прохождении (один раз)
- Привязка результатов к группе пользователя (если он в одной группе)

### 📊 Результаты и статистика
- История тестов пользователя
- График среднего балла по темам
- Экспорт результатов в CSV

### 👨‍🏫 Кабинет методиста
- **📋 Редактор вопросов:** список, фильтры (тема, поиск, сложность, статус), пагинация
- **➕ Новый вопрос:** форма создания
- **📥 Импорт:** CSV / JSON с валидацией и предпросмотром
- **📤 Экспорт:** CSV / JSON с фильтрами
- **📊 Статистика банка:** графики по темам, сложности, активности
- **Массовые операции:** перемещение по темам, изменение сложности, архивирование, удаление

### 👥 Группы обучения
- Создание/редактирование/деактивация групп
- Назначение куратора
- Состав группы: добавление/удаление участников, роли (`student`/`assistant`/`curator`)
- **📊 Отчёт по группе:** сводка (тесты, средний/лучший балл, прогресс), экспорт в CSV/Excel
- **📄 Протоколы:** создание, закрытие, экспорт

### ⚙️ Администрирование
- Управление пользователями: создание, редактирование, сброс пароля, деактивация
- Генерация надёжных паролей
- Фильтры по роли/статусу, поиск
- Защита от самоблокировки
- Логирование всех действий (`audit_log`)

---

## 🏗️ Структура проекта

```
attestation_streamlit/
├── app.py                              # точка входа (логин + главная)
├── config.py                           # конфигурация (.env)
├── database.py                         # слой работы с MySQL
├── requirements.txt
├── .env                                # НЕ коммитить (в .gitignore)
├── .env.example                        # шаблон переменных окружения
├── .gitignore
├── README.md
├── pages/
│   ├── 1_📝_Тестирование.py
│   ├── 2_📊_Результаты.py
│   ├── 3_👤_Профиль.py
│   ├── 4_⚙️_Администрирование.py       # admin
│   ├── 5_👨‍🏫_Методист.py               # methodist + admin
│   └── 6_👥_Группы.py                  # methodist + admin
├── utils/
│   ├── __init__.py
│   ├── auth.py                         # require_login / require_admin / require_methodist
│   ├── user_io.py                      # валидация, генерация паролей, роли
│   ├── question_io.py                  # импорт/экспорт вопросов
│   └── protocol_io.py                  # генерация отчётов и протоколов
├── migrations/
│   ├── 001_extend_questions.sql
│   └── 002_groups.sql
├── logs/                               # (в .gitignore)
└── static/
```

---

## 🗄️ Схема БД

| Таблица | Назначение |
|---|---|
| `users` | Пользователи, роли, пароли (sha256+salt) |
| `questions` | Вопросы: тема, текст, варианты, правильный ответ, сложность, теги, активность |
| `questions_history` | История изменений вопросов |
| `results` | Результаты тестов, привязка к `user_id`, `group_id`, `protocol_id` |
| `audit_log` | Журнал действий пользователей |
| `groups` | Группы обучения |
| `group_members` | Участники групп (many-to-many, роли в группе) |
| `protocols` | Протоколы тестирования по группам |

> ⚠️ Таблица `groups` — зарезервированное имя в MySQL 8. Везде используется экранирование: `` `groups` ``.

---

## 🚀 Установка

### Требования
- Ubuntu 22.04+ / 24.04+
- Python 3.11+
- MySQL 8.0+
- Nginx
- systemd

### 1. Клонировать репозиторий

```bash
git clone git@github.com:USERNAME/attestation_streamlit.git
cd attestation_streamlit
```

### 2. Виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настроить `.env`

```bash
cp .env.example .env
nano .env
```

Пример:

```env
FLASK_ENV=production
DEBUG=False
SECRET_KEY=сгенерируйте-случайную-строку

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=attestation_user
MYSQL_PASSWORD=Secure_Password_123!
MYSQL_DATABASE=attestation_db

APP_NAME=Система аттестации
QUESTIONS_PER_TEST=10
PASSWORD_MIN_LENGTH=6
```

### 4. Создать БД и пользователя MySQL

```bash
sudo mysql -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS attestation_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'attestation_user'@'localhost'
  IDENTIFIED BY 'Secure_Password_123!';

GRANT ALL PRIVILEGES ON attestation_db.* TO 'attestation_user'@'localhost';
FLUSH PRIVILEGES;
SQL
```

### 5. Инициализировать схему

```bash
.venv/bin/python -c "
from database import Database
db = Database()
db.init_db()
db.add_default_users()
db.add_sample_questions()
print('✅ Готово')
"
```

### 6. Запустить Streamlit

Вручную (для проверки):

```bash
.venv/bin/streamlit run app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
```

Или через systemd — см. раздел **Деплой**.

---

## ⚙️ Деплой (systemd + Nginx)

### `systemd` unit

Файл `/etc/systemd/system/attestation-streamlit.service`:

```ini
[Unit]
Description=Streamlit Attestation System
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=leocrochet
Group=leocrochet
WorkingDirectory=/home/leocrochet/PycharmProjects/attestation_streamlit

ExecStart=/home/leocrochet/PycharmProjects/attestation_streamlit/.venv/bin/streamlit run app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Применить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now attestation-streamlit
sudo systemctl status attestation-streamlit
```

### Nginx

Файл `/etc/nginx/sites-available/attestation`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/attestation /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### SSL (Certbot)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo systemctl enable --now certbot.timer
```

---

## 👤 Учётные записи по умолчанию

⚠️ **Смените пароли перед продакшеном!**

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin123` | Администратор |
| `user` | `user123` | Пользователь |

Создать методиста:

1. Войти под `admin`
2. `⚙️ Администрирование` → `👥 Пользователи` → **➕ Создать пользователя**
3. Логин `methodist`, роль **👨‍🏫 Методист**, пароль — сгенерировать

---

## 🔧 Полезные команды

```bash
# Статус
sudo systemctl status attestation-streamlit

# Логи в реальном времени
sudo journalctl -u attestation-streamlit -f

# Перезапуск
sudo systemctl restart attestation-streamlit

# Проверить порт
sudo ss -tlnp | grep 8501
curl -I http://127.0.0.1:8501/

# Проверить MySQL
mysql -u attestation_user -p attestation_db -e "SHOW TABLES;"

# Проверить Nginx
sudo nginx -t && sudo systemctl reload nginx
```

---

## 🧪 Полезные SQL-запросы

```sql
-- Все пользователи
SELECT id, username, full_name, role, is_active FROM users;

-- Все группы с числом участников
SELECT g.id, g.name, COUNT(gm.id) AS members
FROM `groups` g
LEFT JOIN group_members gm ON gm.group_id = g.id AND gm.is_active = TRUE
GROUP BY g.id;

-- Результаты по группе
SELECT u.full_name, r.topic, r.score, r.total_questions, r.date
FROM results r
JOIN users u ON u.id = r.user_id
WHERE r.group_id = 1
ORDER BY r.date DESC;

-- Журнал действий
SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20;
```

---

## 🔒 Безопасность

- **Пароли:** хранятся как `sha256(salt + password)` — с солью на каждого пользователя
- **.env:** не коммитится, добавлен в `.gitignore`
- **Роли:** проверка на каждой странице через `require_*` из `utils/auth.py`
- **Логирование:** все важные действия пишутся в `audit_log`
- **CSRF/XSRF:** включён Streamlit по умолчанию

### TODO перед продакшеном
- [ ] Сменить пароли `admin` / `user`
- [ ] Сменить `SECRET_KEY` в `.env`
- [ ] Убрать блок «Тестовые учётные записи» из боковой панели `app.py`
- [ ] Настроить SSL (Certbot)
- [ ] Настроить регулярный бэкап БД (`mysqldump` + cron)
- [ ] Включить `fail2ban` для SSH
- [ ] Перейти с `sha256` на `bcrypt`/`argon2`

---

## 🛠️ Разработка

```bash
# Создать ветку
git checkout -b feature/название

# Правки кода

# Проверить синтаксис
python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"

# Запустить локально
.venv/bin/streamlit run app.py --server.port 8501 --server.headless true

# Коммит и push
git add .
git commit -m "Описание изменений"
git push -u origin feature/название
```

Затем на GitHub — **Pull Request** в `main`.

---

## 🗺️ Roadmap

- [x] Аутентификация с ролями
- [x] Тестирование и результаты
- [x] Управление пользователями (админ)
- [x] Управление вопросами (методист): CRUD, импорт/экспорт
- [x] Группы обучения
- [x] Отчёты по группам (CSV/Excel)
- [x] Протоколы тестирования (базовая версия)
- [ ] **Назначение тестов группе** (задание с дедлайном)
- [ ] **PDF-протокол** с шапкой и подписями
- [ ] **Дашборд методиста** по всем группам
- [ ] **Выбор группы** при тесте (если пользователь в нескольких)
- [ ] **Тесты (pytest)** для `database.py` и `utils/`
- [ ] **CI/CD** через GitHub Actions
- [ ] **Docker + docker-compose**
- [ ] **Мультиязычность** (RU/EN)
- [ ] **Мониторинг и алерты** (Telegram-бот)

---

## 📄 Лицензия