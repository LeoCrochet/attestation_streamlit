#!/bin/bash
#
# Скрипт установки системы аттестации на Streamlit
# Для Debian 13 (Trixie)
# Предполагает, что MariaDB уже установлена и настроена
#

set -e

# ==================== ЦВЕТА ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ==================== ПАРАМЕТРЫ ====================
APP_DIR="/opt/attestation_streamlit"
APP_USER="attestation"
DB_NAME="attestation_db"
DB_USER="attestation_user"
DB_PASS="Secure_Password_123!"
DB_HOST="localhost"
DB_PORT="3306"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Установка системы аттестации${NC}"
echo -e "${BLUE}  Debian 13 (Trixie)${NC}"
echo -e "${BLUE}========================================${NC}"

# ==================== ПРОВЕРКА ROOT ====================
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Запустите с правами root: sudo ./setup.sh${NC}"
    exit 1
fi

# ==================== ПРОВЕРКА MARIADB ====================
echo -e "\n${YELLOW}[1/7] Проверка MariaDB...${NC}"

if ! systemctl is-active --quiet mariadb; then
    echo -e "${RED}❌ MariaDB не запущена. Запустите: sudo systemctl start mariadb${NC}"
    exit 1
fi

# Проверка подключения к БД
if ! mariadb -u "${DB_USER}" -p"${DB_PASS}" -e "USE ${DB_NAME};" 2>/dev/null; then
    echo -e "${RED}❌ Не удалось подключиться к БД ${DB_NAME} от имени ${DB_USER}${NC}"
    echo -e "${YELLOW}Проверьте, что база и пользователь созданы:${NC}"
    echo -e "  sudo mariadb"
    echo -e "  CREATE DATABASE ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    echo -e "  CREATE USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
    echo -e "  GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
    echo -e "  FLUSH PRIVILEGES;"
    exit 1
fi

echo -e "${GREEN}✅ MariaDB работает, БД доступна${NC}"

# ==================== УСТАНОВКА БАЗОВЫХ ПАКЕТОВ ====================
echo -e "\n${YELLOW}[2/7] Установка базовых пакетов...${NC}"

# ВАЖНО: БЕЗ software-properties-common (его нет в Debian 13)
apt update
apt install -y \
    wget curl git vim nano htop net-tools \
    apt-transport-https ca-certificates gnupg \
    build-essential python3-dev python3-pip \
    python3-venv python3-wheel libssl-dev libffi-dev \
    pkg-config nginx fail2ban openssl rsync socat

# ==================== ПОДГОТОВКА ПРОЕКТА ====================
echo -e "\n${YELLOW}[3/7] Подготовка проекта...${NC}"

# Создание пользователя приложения
useradd -m -s /bin/bash ${APP_USER} 2>/dev/null || true
usermod -a -G www-data ${APP_USER}

# Копирование проекта
CURRENT_DIR=$(pwd)
if [ ! -f "${CURRENT_DIR}/app.py" ]; then
    echo -e "${RED}❌ Не найден app.py в текущей директории${NC}"
    echo -e "${YELLOW}Запустите скрипт из директории проекта${NC}"
    exit 1
fi

mkdir -p ${APP_DIR}
cp -r ${CURRENT_DIR}/* ${APP_DIR}/ 2>/dev/null || true

# Создание директории для логов
mkdir -p ${APP_DIR}/logs

# Права доступа
chown -R ${APP_USER}:www-data ${APP_DIR}
chmod -R 755 ${APP_DIR}

# ==================== ВИРТУАЛЬНОЕ ОКРУЖЕНИЕ ====================
echo -e "\n${YELLOW}[4/7] Настройка Python окружения...${NC}"

su - ${APP_USER} -c "cd ${APP_DIR} && python3 -m venv venv"
su - ${APP_USER} -c "${APP_DIR}/venv/bin/pip install --upgrade pip setuptools wheel"

# Установка зависимостей
if [ -f "${APP_DIR}/requirements.txt" ]; then
    su - ${APP_USER} -c "${APP_DIR}/venv/bin/pip install -r ${APP_DIR}/requirements.txt"
else
    su - ${APP_USER} -c "${APP_DIR}/venv/bin/pip install streamlit pandas plotly PyMySQL python-dotenv"
fi

# ==================== НАСТРОЙКА ОКРУЖЕНИЯ ====================
echo -e "\n${YELLOW}[5/7] Настройка окружения...${NC}"

# Создание .env
cat > ${APP_DIR}/.env <<EOF
FLASK_ENV=production
DEBUG=False
SECRET_KEY=$(openssl rand -base64 32)
MYSQL_HOST=${DB_HOST}
MYSQL_PORT=${DB_PORT}
MYSQL_USER=${DB_USER}
MYSQL_PASSWORD=${DB_PASS}
MYSQL_DATABASE=${DB_NAME}
APP_NAME=Система аттестации
APP_VERSION=1.0.0
QUESTIONS_PER_TEST=10
PASSWORD_MIN_LENGTH=6
EOF

chown ${APP_USER}:www-data ${APP_DIR}/.env
chmod 600 ${APP_DIR}/.env

# ==================== НАСТРОЙКА СЕРВИСОВ ====================
echo -e "\n${YELLOW}[6/7] Настройка сервисов...${NC}"

# Создание systemd сервиса
cat > /etc/systemd/system/attestation-streamlit.service <<EOF
[Unit]
Description=Streamlit Attestation System
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=${APP_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin"
EnvironmentFile=${APP_DIR}/.env

ExecStart=${APP_DIR}/venv/bin/streamlit run app.py \\
    --server.port 8501 \\
    --server.address 127.0.0.1 \\
    --server.enableCORS false \\
    --server.enableXsrfProtection true \\
    --server.headless true \\
    --logger.level info

Restart=always
RestartSec=5

NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateDevices=true

[Install]
WantedBy=multi-user.target
EOF

# Настройка Nginx
cat > /etc/nginx/sites-available/attestation <<'NGINX_EOF'
server {
    listen 80;
    server_name _;

    access_log /var/log/nginx/attestation_access.log;
    error_log /var/log/nginx/attestation_error.log;

    client_max_body_size 100M;

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
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /opt/attestation_streamlit/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_EOF

ln -sf /etc/nginx/sites-available/attestation /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# ==================== ИНИЦИАЛИЗАЦИЯ И ЗАПУСК ====================
echo -e "\n${YELLOW}[7/7] Инициализация БД и запуск...${NC}"

# Инициализация схемы БД
echo -e "${YELLOW}Инициализация схемы БД...${NC}"
su - ${APP_USER} -c "cd ${APP_DIR} && ${APP_DIR}/venv/bin/python -c \"
from database import Database
db = Database()
db.init_db()
db.add_default_users()
db.add_sample_questions()
print('✅ База данных инициализирована')
\""

# Запуск сервисов
nginx -t && systemctl restart nginx
systemctl daemon-reload
systemctl enable attestation-streamlit
systemctl start attestation-streamlit

# Проверка статуса
sleep 3
if systemctl is-active --quiet attestation-streamlit; then
    SERVICE_STATUS="${GREEN}✅ Запущен${NC}"
else
    SERVICE_STATUS="${RED}❌ Ошибка запуска${NC}"
    echo -e "${RED}Проверьте логи:${NC}"
    echo -e "  sudo journalctl -u attestation-streamlit -n 30 --no-pager"
fi

# ==================== ИТОГ ====================
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Установка завершена!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Приложение:  ${YELLOW}http://$(hostname -I | awk '{print $1}')${NC}"
echo -e "Статус:      ${SERVICE_STATUS}"
echo ""
echo -e "${YELLOW}Пароль приложения:${NC} ${APP_DIR}/.env"
echo ""
echo -e "Тестовые учётные записи:"
echo -e "  🔑 admin    / admin123"
echo -e "  👤 user     / user123"
echo -e "  💼 manager  / manager123"
echo ""
echo -e "Управление сервисом:"
echo -e "  ${GREEN}sudo systemctl status attestation-streamlit${NC}"
echo -e "  ${GREEN}sudo systemctl restart attestation-streamlit${NC}"
echo -e "  ${GREEN}sudo journalctl -u attestation-streamlit -f${NC}"
echo ""
echo -e "Проверка БД:"
echo -e "  ${GREEN}mariadb -u ${DB_USER} -p${DB_PASS} -e 'USE ${DB_NAME}; SHOW TABLES;'${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"