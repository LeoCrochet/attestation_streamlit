import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv('MYSQL_HOST'),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DATABASE')
)
cursor = conn.cursor()

alter_queries = [
    # 1. Добавляем поля организации в таблицу групп
    "ALTER TABLE `groups` ADD COLUMN organization_name VARCHAR(255) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN organization_address VARCHAR(255) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN organization_phone VARCHAR(100) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN organization_email VARCHAR(100) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN contact_person VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE `groups` ADD COLUMN manager_name VARCHAR(150) DEFAULT NULL",
    
    # 2. Добавляем поля из таблицы заявки в участников группы
    "ALTER TABLE group_members ADD COLUMN profession VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN education VARCHAR(150) DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN birth_year INT DEFAULT NULL",
    "ALTER TABLE group_members ADD COLUMN training_type VARCHAR(100) DEFAULT NULL"
]

for q in alter_queries:
    try:
        cursor.execute(q)
        print(f"✅ {q}")
    except mysql.connector.Error as err:
        if err.errno == 1060: # Duplicate column
            print(f"⏭ Уже существует: {q}")
        else:
            print(f"❌ Ошибка: {err}")

conn.commit()
cursor.close()
conn.close()
print("🎉 База обновлена!")