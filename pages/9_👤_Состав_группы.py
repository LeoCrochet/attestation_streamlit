"""👤 Состав конкретной группы."""
import streamlit as st
import pandas as pd
import os
import random
import time
from datetime import datetime

from utils.session import restore_session
from utils.navigation import setup_page
from database import Database
from utils.auth import require_login
from utils.excel_protocol import generate_protocol_xlsx

st.set_page_config(page_title="Состав группы", page_icon="👤", layout="wide")
restore_session()
setup_page()
require_login()

if st.session_state.get("role") not in ("methodist", "admin", "manager"):
    st.error("⛔ Доступ только для методиста, менеджера или администратора")
    st.stop()

@st.cache_resource
def get_db():
    return Database()

db = get_db()
USER = st.session_state.user
USER_ID = st.session_state.user_id

# --- ПОЛУЧАЕМ ID ГРУППЫ ИЗ URL ИЛИ SESSION_STATE ---
group_id = st.query_params.get("group_id")
if not group_id and "current_group_id" in st.session_state:
    group_id = st.session_state["current_group_id"]
    st.query_params["group_id"] = str(group_id)

if not group_id:
    st.warning("Группа не выбрана. Вернитесь в список групп.")
    if st.button("← Назад к группам"):
        st.switch_page("pages/6_👥_Группы.py")
    st.stop()

try:
    group_id = int(group_id)
except ValueError:
    st.error("Неверный ID группы")
    st.stop()

group = db.get_group_by_id(group_id)
if not group:
    st.error("Группа не найдена")
    st.stop()

st.title(f"👤 Состав группы: {group['name']}")

if st.button("← Вернуться к списку групп", type="secondary"):
    st.switch_page("pages/6_👥_Группы.py")

st.caption(f"**Куратор:** {group.get('curator_name') or '—'} | **Организация:** {group.get('organization_name') or '—'}")

members = db.get_group_members(group["id"], only_active=True)

# --- БЛОК ЗАВЕРШЕНИЯ ОБУЧЕНИЯ ---
if group["is_active"]:
    with st.expander("🛑 Завершение обучения", expanded=False):
        st.warning("⚠️ **Внимание!** Завершение обучения заблокирует пересдачи и сгенерирует итоговый протокол.")
        if st.button("Завершить обучение группы", type="primary"):
            protocol_id = db.finish_group_training(group["id"], st.session_state.user)
            detailed = db.get_group_results_detailed(group["id"])
            
            try:
                os.makedirs("protocols", exist_ok=True)
                file_path = f"protocols/protocol_group_{group['id']}_{protocol_id}.xlsx"
                
                protocol_bytes = generate_protocol_xlsx(
                    group=group, 
                    members=members,
                    detailed_results=detailed,
                    date_str=datetime.now().strftime("%d.%m.%Y")
                )
                
                with open(file_path, "wb") as f:
                    f.write(protocol_bytes)
                
                db.save_protocol_file_path(protocol_id, file_path)
                db.log_action(st.session_state.user_id, "group_finish", f"Обучение завершено, протокол #{protocol_id}")
                
                st.success(f"✅ Обучение завершено! Протокол сохранен на сервере (ID: {protocol_id}).")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка генерации протокола: {e}")
else:
    st.info("🏁 Обучение по этой группе завершено. Редактирование состава заблокировано.")

# --- ТАБЛИЦА УЧАСТНИКОВ ---
if members:
    df_members = pd.DataFrame([
        {
            "ID": m["user_id"],
            "ФИО": m["full_name"] or "—",
            "Профессия": m.get("profession") or "—",
            "Образование": m.get("education") or "—",
            "Год рожд.": m.get("birth_year") or "—",
            "Вид обучения": m.get("training_type") or "—",
            "Логин": m["username"],
            "Роль": m["role_in_group"],
        }
        for m in members
    ])
    st.dataframe(df_members, use_container_width=True, hide_index=True)

    # --- УДАЛЕНИЕ ИЗ ГРУППЫ ---
    with st.expander("🚫 Удалить участника из группы", expanded=False):
        if group["is_active"]:
            rm_map = {
                f"{m['full_name'] or m['username']} ({m['username']})": m["user_id"]
                for m in members
            }
            rm_label = st.selectbox("Пользователь", list(rm_map.keys()), key="gm_rm")
            if st.button("Удалить из группы", key="gm_rm_btn"):
                db.remove_group_member(group["id"], rm_map[rm_label])
                db.log_action(USER_ID, "group_member_remove",
                              f"Удалён из группы {group['name']}: {rm_label}")
                st.success("Пользователь удалён из группы")
                st.rerun()
        else:
            st.info("🔒 Группа завершена. Изменение состава заблокировано.")
else:
    st.info("В группе пока нет участников")

# --- ДОБАВЛЕНИЕ УЧАСТНИКА ---
st.divider()
with st.expander("➕ Добавить одного участника вручную", expanded=False):
    if group["is_active"]:
        existing_ids = {m["user_id"] for m in members}
        all_users = db.get_all_users(include_inactive=False)
        candidates = [u for u in all_users if u["id"] not in existing_ids]

        if not candidates:
            st.info("Все пользователи уже в группе")
        else:
            add_map = {
                f"{u['full_name'] or u['username']} ({u['username']})": u["id"]
                for u in candidates
            }
            
            add_label = st.selectbox("Выберите пользователя", list(add_map.keys()), key="gm_add_user")
            
            c1, c2 = st.columns(2)
            with c1:
                profession = st.text_input("Профессия (разряд)", key="gm_prof")
                education = st.text_input("Образование", key="gm_edu")
            with c2:
                birth_year = st.number_input("Год рождения", min_value=1940, max_value=2020, value=1990, step=1, key="gm_year")
                training_type = st.selectbox(
                    "Вид обучения", 
                    ["Первичное", "Периодическая проверка", "Повышение квалификации"], 
                    key="gm_train"
                )

            if st.button("✅ Добавить в группу", type="primary", key="gm_add_btn"):
                if not add_label:
                    st.warning("Выберите пользователя")
                else:
                    db.add_group_member(
                        group_id=group["id"], 
                        user_id=add_map[add_label], 
                        role_in_group="student",
                        profession=profession or None,
                        education=education or None,
                        birth_year=birth_year or None,
                        training_type=training_type
                    )
                    db.log_action(USER_ID, "group_member_add",
                                  f"Добавлен в {group['name']}: {add_label}")
                    st.success(f"✅ Пользователь добавлен")
                    st.rerun()
    else:
        st.info("🔒 Группа завершена. Изменение состава заблокировано.")

# --- МАССОВЫЙ ИМПОРТ ИЗ ЗАЯВКИ ---
st.divider()
with st.expander("📥 Импорт заявки (Excel/CSV)", expanded=False):
    if group["is_active"]:
        template_df = pd.DataFrame({
            "ФИО": ["Иванов Иван Иванович"], 
            "Профессия": ["Электромонтер 4 разряда"], 
            "Образование": ["Среднее специальное"], 
            "Год рождения": [1985], 
            "Вид обучения": ["Первичное"]
        })
        csv_template = template_df.to_csv(index=False, sep=';', encoding='utf-8-sig')
        
        st.download_button(
            label="📄 Скачать шаблон заявки (CSV)",
            data=csv_template.encode('utf-8-sig'),
            file_name="shablon_zayavki.csv",
            mime="text/csv",
            help="Заполните этот файл в Excel и загрузите обратно"
        )

        uploaded_file = st.file_uploader("Загрузите заполненную заявку", type=["xlsx", "csv"], key="application_uploader")
        
        if uploaded_file is not None:
            if st.button("🚀 Импортировать сотрудников", type="primary", key="btn_import_app"):
                from utils.import_application import parse_application_excel
                
                data, err = parse_application_excel(uploaded_file.read())
                
                if err:
                    st.error(err)
                elif not data:
                    st.warning("В файле не найдено ни одного корректного ФИО")
                else:
                    st.info(f"Файл прочитан. Найдено сотрудников: {len(data)}. Начинаю импорт...")
                    
                    added_count = 0
                    created_count = 0
                    
                    for person in data:
                        fio = person["fio"]
                        all_db_users = db.get_all_users(include_inactive=True)
                        user = next((u for u in all_db_users if u["full_name"] and u["full_name"].strip().lower() == fio.strip().lower()), None)
                        
                        if not user:
                            username = f"student_{random.randint(10000, 99999)}"
                            default_password = "123456"
                            user_id = db.create_user(username=username, password=default_password, full_name=fio, role="user")
                            created_count += 1
                        else:
                            user_id = user["id"]
                            
                        db.add_group_member(group_id=group["id"], user_id=user_id, role_in_group="student",
                            profession=person["profession"], education=person["education"],
                            birth_year=person["birth_year"], training_type=person["training_type"])
                        added_count += 1
                    
                    db.log_action(USER_ID, "group_bulk_import", f"Импорт заявки в {group['name']}: {added_count} чел.")
                    st.success(f"✅ Успешно добавлено: {added_count} чел. (Создано аккаунтов: {created_count})")
                    time.sleep(1.5)
                    st.rerun()
    else:
        st.info("🔒 Группа завершена. Импорт сотрудников заблокирован.")