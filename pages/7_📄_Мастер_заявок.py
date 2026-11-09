"""📄 Мастер заявок — автоматическое создание группы и задания."""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils.session import restore_session
from database import Database
from utils.auth import require_methodist
from utils.import_application import parse_application_excel
from utils.import_word import parse_application_word

st.set_page_config(page_title="Мастер заявок", page_icon="📄", layout="wide")
restore_session()
from utils.navigation import setup_page
setup_page()
require_methodist()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

# --- Универсальная функция очистки ---
def _clean(val):
    if val is None:
        return None
    if isinstance(val, dict):
        # Если пришел словарь, пытаемся вытащить хоть что-то осмысленное
        return str(list(val.values())[0]) if val else None
    if isinstance(val, (str, int, float, bool)):
        return val
    return str(val)

st.title("📄 Мастер заявок")
st.caption("Загрузите заявку, чтобы автоматически создать группу, участников и задание")

# ==================================================================
# 1. ЗАГРУЗКА ФАЙЛА
# ==================================================================
st.subheader("1. Загрузите заявку")
st.write("Поддерживаются форматы Excel (.xlsx), CSV (.csv) и Word (.docx).")

uploaded_file = st.file_uploader("Выберите файл заявки", type=["xlsx", "csv", "docx"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    fname = uploaded_file.name.lower()
    
    # Парсим файл
    if fname.endswith(".docx"):
        data, err = parse_application_word(file_bytes)
    else:
        data, err = parse_application_excel(file_bytes)
        
    if err:
        st.error(f"Ошибка чтения файла: {err}")
    elif not data:
        st.warning("В файле не найдено ни одного сотрудника.")
    else:
        st.success(f"✅ Файл прочитан. Найдено сотрудников: **{len(data)}**")
        
        with st.expander("Предпросмотр списка (первые 5)", expanded=False):
            for p in data[:5]:
                st.write(f"• **{_clean(p['fio'])}** — {_clean(p.get('profession')) or '—'}")
            if len(data) > 5:
                st.write("...")
                
        st.divider()
        st.subheader("2. Параметры группы")
        
        with st.form("wizard_form"):
            c1, c2 = st.columns(2)
            with c1:
                default_name = f"Группа {datetime.now().strftime('%d.%m.%Y_%H%M')}"
                group_name = st.text_input("Название группы *", value=default_name)
                org_name = st.text_input("Организация (Заказчик)")
                org_address = st.text_area("Адрес", height=68)
                g_start_date = st.date_input("Дата начала обучения", value=date.today())
            with c2:
                manager_name = st.text_input("Руководитель организации")
                contact_person = st.text_input("Контактное лицо")
                
            st.divider()
            st.subheader("3. Параметры задания (теста)")
            
            c3, c4 = st.columns(2)
            with c3:
                topics = ["Все темы"] + db.get_all_topics(include_archived=False)
                a_topic = st.selectbox("Тема теста", topics)
                a_num = st.number_input("Количество вопросов", 1, 100, 10)
            with c4:
                a_attempts = st.number_input("Макс. попыток", 1, 10, 1)
                a_pass = st.slider("Проходной балл, %", 0, 100, 60, 5)
                a_time = st.number_input("Ограничение времени, мин (0 = без)", 0, 300, 0)
                
            submitted = st.form_submit_button("🚀 Создать группу и задание", type="primary")
            
            if submitted:
                if not group_name.strip():
                    st.error("Укажите название группы")
                else:
                    try:
                        # 1. Создаем группу
                        gid = db.create_group(
                            name=group_name.strip(),
                            description=f"Организация: {org_name}",
                            created_by=st.session_state.user,
                            start_date=g_start_date
                        )
                        
                        if not gid:
                            st.error("Ошибка: не удалось создать группу (возможно, имя занято).")
                            st.stop()

                        # Дописываем данные организации
                        db.execute_query("""
                            UPDATE `groups` 
                            SET organization_name=%s, organization_address=%s, 
                                contact_person=%s, manager_name=%s
                            WHERE id=%s
                        """, (str(org_name), str(org_address), str(contact_person), str(manager_name), gid), commit=True)
                        
                        # 2. Создаем задание для этой группы
                        topic_value = None if a_topic == "Все темы" else str(a_topic)
                        time_limit = int(a_time) if a_time > 0 else None
                        
                        aid = db.create_assignment(
                            group_id=int(gid), 
                            topic=topic_value,
                            num_questions=int(a_num), 
                            max_attempts=int(a_attempts),
                            time_limit_min=time_limit, 
                            pass_score=int(a_pass),
                            title=f"Аттестация по заявке от {datetime.now().strftime('%d.%m.%Y')}",
                            description="Автоматически создано из заявки",
                            created_by=str(st.session_state.user)
                        )
                        
                        # 3. Создаем пользователей и добавляем в группу
                        added_count = 0
                        created_count = 0
                        
                        for person in data:
                            fio = _clean(person.get("fio"))
                            if not fio:
                                continue
                            
                            # Ищем пользователя по ФИО
                            all_users = db.get_all_users(include_inactive=True)
                            user = next((u for u in all_users if u["full_name"] and u["full_name"].strip().lower() == fio.lower()), None)
                            
                            # Создаем, если нет
                            if not user:
                                import random
                                username = f"student_{random.randint(10000, 99999)}"
                                default_password = "123456"
                                
                                # Защита от дублей username при генерации
                                max_tries = 5
                                while max_tries > 0:
                                    try:
                                        user_id = db.create_user(
                                            username=username,
                                            password=default_password,
                                            full_name=fio,
                                            role="user"
                                        )
                                        if isinstance(user_id, dict):
                                            user_id = user_id.get("id")
                                        break
                                    except Exception:
                                        username = f"student_{random.randint(10000, 99999)}"
                                        max_tries -= 1
                                
                                created_count += 1
                            else:
                                user_id = user["id"]
                                
                            # Безопасно извлекаем строки
                            prof = _clean(person.get("profession"))
                            edu = _clean(person.get("education"))
                            train = _clean(person.get("training_type")) or "Первичное"
                            
                            # Бронебойная обработка года рождения
                            year = None
                            raw_year = person.get("birth_year")
                            if raw_year is not None and not isinstance(raw_year, dict):
                                import re
                                match = re.search(r'\d{4}', str(raw_year))
                                if match:
                                    year = int(match.group())
                            
                            # Добавляем в группу
                            db.add_group_member(
                                group_id=int(gid),
                                user_id=int(user_id),
                                role_in_group="student",
                                profession=prof,
                                education=edu,
                                birth_year=year,
                                training_type=train
                            )
                            added_count += 1
                        
                        db.log_action(st.session_state.user_id, "wizard_create", 
                                      f"Создана группа {group_name} и задание #{aid}. Добавлено: {added_count} чел.")
                        
                        st.success(f"""
                        ✅ **Успешно создано!**
                        * **Группа:** {group_name} (ID: {gid})
                        * **Задание:** ID {aid} (Тема: {a_topic})
                        * **Участников:** {added_count} (создано новых аккаунтов: {created_count})
                        """)
                        
                        st.info("👉 Перейдите в раздел «👥 Группы», чтобы увидеть состав, или в «👨‍🏫 Методист -> 📌 Задания», чтобы следить за прохождением.")
                        
                    except Exception as e:
                        st.error(f"Ошибка при создании: {e}")