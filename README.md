# 🎓 Система аттестации

Веб-приложение для проведения аттестации и обучения персонала: тестирование сотрудников, управление банком вопросов, группами обучения, заданиями, отчётами и протоколами.

**Стек:** Python 3.11+ · Streamlit · MySQL 8 (MariaDB) · Nginx · systemd · Ubuntu 24.04+

## ✨ Возможности

### 🔐 Аутентификация и роли
| Роль | Что доступно |
|---|---|
| **user** | Тестирование, результаты, профиль |
| **manager** | То же, что user (расширения в разработке) |
| **methodist** | Всё выше + Дашборд, Методист, Группы, Задания, Мастер заявок, Сурогат |
| **admin** | Всё выше + Администрирование пользователей |

### 📈 Дашборд (methodist/admin)
Сводные метрики, график успеваемости, качество знаний по профессиям, динамика по месяцам, список отстающих. Активные задания с быстрым переходом к деталям.
*(Тесты админов и методистов исключены из статистики).*

### 📝 Тестирование
Активные задания с прогресс-баром, подсветкой дедлайна и таймером. Режим сурогата (прохождение теста от имени сотрудника).

### 📊 Результаты
Пользователи видят личную историю. Методисты и админы видят сводную таблицу всех результатов с фильтрами и просмотром деталей.

### 👨‍🏫 Кабинет методиста
Банк вопросов (CRUD, массовые действия, импорт/экспорт CSV/JSON). Статистика банка и анализ «проблемных» вопросов.

### 📌 Управление заданиями
Создание заданий с дедлайнами и лимитами. Карточный вид, модальные окна для просмотра деталей и редактирования. Закрытие/открытие и архивация.

### 👥 Группы обучения
Создание групп, управление составом (профессии, образование), импорт из Excel/CSV, завершение обучения с генерацией протокола Excel.

### 📄 Мастер заявок
Загрузка заявки в Word/Excel/CSV, автоматический парсинг организации и списка сотрудников, генерация названия группы.

### 🎯 Режим сурогата
Быстрое прохождение теста от имени сотрудника с сохранением результата в его профиль.

## 🏗️ Структура проекта

```text
attestation_streamlit/
├── app.py                        # Главная (логин, помощник, навигация)
├── config.py                     # Конфигурация (.env)
├── database.py                   # Слой работы с MySQL
├── db_schema.py                  # Единая схема БД (CREATE TABLE, ALTER)
├── init_database.py              # Скрипт инициализации БД
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── config.toml               # Настройки темы и скрытие меню
├── pages/
│   ├── 0_📈_Дашборд.py
│   ├── 1_📝_Тестирование.py
│   ├── 2_📊_Результаты.py
│   ├── 3_👤_Профиль.py
│   ├── 4_⚙️_Администрирование.py
│   ├── 5_👨‍🏫_Методист.py
│   ├── 6_👥_Группы.py
│   ├── 7_📄_Мастер_заявок.py
│   ├── 8_🎯_Сурогат.py
│   ├── 9_👤_Состав_группы.py
│   └── 10_📌_Задания.py
├── utils/
│   ├── auth.py                   # Проверки ролей
│   ├── navigation.py             # Навигация, логин, кнопка скрытия панели
│   ├── session.py                # Восстановление сессии из URL
│   ├── user_io.py                # Валидация, генерация паролей
│   ├── question_io.py            # Импорт/экспорт вопросов
│   ├── protocol_io.py            # Отчёты и протоколы
│   ├── excel_protocol.py         # Генерация протокола комиссии
│   ├── word_export.py            # Разбор ответов в Word
│   ├── import_application.py     # Парсинг Excel/CSV заявок
│   └── import_word.py            # Парсинг Word заявок
├── templates/
│   └── application_template.docx # Утверждённый шаблон заявки
└── migrations/                   # SQL-скрипты (очистка тестов и т.д.)
### 🚀 Установка (локально)
Клонируйте репозиторий:

bash
git clone git@github.com:LeoCrochet/attestation_streamlit.git
cd attestation_streamlit
Создайте виртуальное окружение и установите зависимости:

bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Настройте .env:

bash
cp .env.example .env
nano .env
Заполните параметры MySQL и SECRET_KEY.

Создайте БД и пользователя в MySQL:

sql
CREATE DATABASE attestation_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'attestation_user'@'localhost' IDENTIFIED BY 'Secure_Password_123!';
GRANT ALL PRIVILEGES ON attestation_db.* TO 'attestation_user'@'localhost';
FLUSH PRIVILEGES;
Инициализируйте схему:

bash
python init_database.py
Запустите Streamlit:

bash
streamlit run app.py
⚙️ Деплой (Production)
На сервере (Ubuntu) Streamlit настроен как служба systemd, а обновления подтягиваются через GitHub Actions при пуше в ветку develop.

Настройка службы systemd
Файл /etc/systemd/system/attestation-streamlit.service:

ini
[Unit]
Description=Streamlit Attestation System
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/attestation_streamlit
Environment="PATH=/opt/attestation_streamlit/venv/bin"
ExecStart=/opt/attestation_streamlit/venv/bin/python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
Активация: sudo systemctl daemon-reload && sudo systemctl enable --now attestation-streamlit

Автодеплой (GitHub Actions)
На сервере установлен и запущен Self-Hosted Runner (пользователь github-runner).
Workflow-файл .github/workflows/deploy.yml:

yaml
name: Deploy to Production
on:
  push:
    branches: [ "develop" ]
jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Pull latest changes
        run: |
          cd /opt/attestation_streamlit
          git fetch origin develop
          git reset --hard origin/develop
      - name: Install dependencies
        run: |
          cd /opt/attestation_streamlit
          ./venv/bin/pip install -r requirements.txt
      - name: Restart Streamlit Service
        run: |
          sudo systemctl restart attestation-streamlit
### 🔒 Безопасность
Пароли: хранятся как sha256(salt + password).

.env: не коммитится (в .gitignore).

Роли: проверка на каждой странице через require_*.

Логирование: действия пишутся в audit_log.

### 📄 Лицензия
Проект разработан для внутреннего использования.

text

---

Теперь у вас есть и красивый помощник в интерфейсе, и подробная техническая документация в репозитории. Как только добавите бизнес-процессы, мы дополним вкладки. 👇
