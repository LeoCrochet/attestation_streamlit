"""👥 Управление группами обучения и отчёты."""
from datetime import datetime, date
import time
import random
import os
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.word_export import generate_answers_word
from database import Database
from utils.auth import require_login
from utils.protocol_io import (
    build_group_report_dataframe, build_protocol_dataframe,
    dataframe_to_csv_bytes, dataframe_to_excel_bytes,
)
from utils.excel_protocol import generate_protocol_xlsx
from utils.session import restore_session
from utils.navigation import setup_page

st.set_page_config(page_title="Группы", page_icon="👥", layout="wide")
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

# Функция для всплывающего окна с ответами
@st.dialog("Детали ответов", width="large")
def show_answers_dialog(result_id):
    res = db.get_result_details(result_id)
    if not res:
        st.error("Результат не найден")
        return

    st.write(f"**Студент:** {res['full_name'] or res['username']}")
    st.write(f"**Тема:** {res['topic']} | **Балл:** {res['score']} из {res['total_questions']}")
    st.divider()

    answers = json.loads(res['answers']) if isinstance(res['answers'], str) else res['answers']
    
    if isinstance(answers, dict):
        st.warning("⚠️ Это старый формат ответов. Пройдите тест заново, чтобы увидеть детали.")
        return
        
    for i, ans in enumerate(answers, start=1):
        st.markdown(f"### Вопрос {i}: {ans.get('question_text', '—')}")
        
        opts = ans.get("options", [])
        user_idx = ans.get("user_answer_idx")
        correct_idx = ans.get("correct_answer_idx")
        
        for opt_i, opt_text in enumerate(opts):
            is_user_choice = (opt_i == user_idx)
            is_correct = (opt_i == correct_idx)
            
            if is_correct and is_user_choice:
                st.success(f"✅ **{chr(65 + opt_i)}. {opt_text}** *(Ваш ответ, верно)*")
            elif is_correct:
                st.success(f"✅ **{chr(65 + opt_i)}. {opt_text}** *(Правильный ответ)*")
            elif is_user_choice:
                st.error(f"❌ **{chr(65 + opt_i)}. {opt_text}** *(Ваш ответ, неверно)*")
            else:
                st.write(f"▫️ {chr(65 + opt_i)}. {opt_text}")
        
        st.divider()

    try:
        word_bytes = generate_answers_word(
            user_name=res['full_name'] or res['username'],
            topic=res['topic'],
            score=res['score'],
            total=res['total_questions'],
            answers_data=answers
        )
        st.download_button(
            label="📥 Скачать разбор в Word",
            data=word_bytes,
            file_name=f"answers_{res['username']}_{res['id']}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Ошибка генерации Word: {e}")

st.title("👥 Группы обучения")

tab_list, tab_create, tab_members, tab_report, tab_documents = st.tabs([
    "📋 Список групп",
    "➕ Создать группу",
    "👤 Состав группы",
    "📊 Отчёт по группе",
    "📎 Документы",
])

# ==================================================================
# ВКЛАДКА 1: СПИСОК ГРУПП
# ==================================================================
with tab_list:
    st.subheader("📋 Все группы")

    only_active = st.checkbox("Только активные", value=True, key="g_only_active")
    groups = db.get_all_groups(only_active=only_active)

    if not groups:
        st.info("Групп пока нет. Создайте первую во вкладке ➕.")
    else:
        df = pd.DataFrame([
            {
                "ID": g["id"],
                "Название": g["name"],
                "Описание": g["description"] or "—",
                "Куратор": g["curator_name"] or "—",
                "Участников": g["member_count"],
                "Активна": "✅" if g["is_active"] else "🚫",
                "Создана": g["created_at"].strftime("%d.%m.%Y") if g.get("created_at") else "—",
            }
            for g in groups
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    if groups:
        st.divider()
        with st.expander("🗑️ Удаление и архивация группы", expanded=False):
            group_to_del_map = {f"#{g['id']} — {g['name']}": g for g in groups}
            selected_del_label = st.selectbox("Выберите группу", list(group_to_del_map.keys()), key="del_group_sel")
            selected_del_group = group_to_del_map[selected_del_label]
            
            c1, c2 = st.columns(2)
            
            with c1:
                if selected_del_group["is_active"]:
                    if st.button("🚫 Деактивировать (в архив)", use_container_width=True):
                        protocol_id = db.finish_group_training(selected_del_group["id"], st.session_state.user)
                        members = db.get_group_members(selected_del_group["id"], only_active=True)
                        detailed = db.get_group_results_detailed(selected_del_group["id"])
                        
                        try:
                            os.makedirs("protocols", exist_ok=True)
                            file_path = f"protocols/protocol_group_{selected_del_group['id']}_{protocol_id}.xlsx"
                            
                            protocol_bytes = generate_protocol_xlsx(
                                group=selected_del_group, 
                                members=members,
                                detailed_results=detailed,
                                date_str=datetime.now().strftime("%d.%m.%Y")
                            )
                            
                            with open(file_path, "wb") as f:
                                f.write(protocol_bytes)
                            
                            db.save_protocol_file_path(protocol_id, file_path)
                            db.log_action(USER_ID, "group_archive", f"Группа в архиве с протоколом #{protocol_id}: {selected_del_group['name']}")
                            
                            st.success(f"✅ Группа в архиве. Протокол #{protocol_id} сохранен.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка генерации протокола: {e}")
                else:
                    st.info("Группа уже в архиве")
                    
            with c2:
                confirm_key = f"confirm_del_grp_{selected_del_group['id']}"
                if st.session_state.get(confirm_key):
                    st.warning(f"⚠️ Удалить **«{selected_del_group['name']}»** навсегда? Все результаты и задания будут удалены!")
                    if st.button("🔥 Да, удалить навсегда", type="primary", use_container_width=True):
                        db.hard_delete_group(selected_del_group["id"])
                        db.log_action(USER_ID, "group_hard_delete", f"Группа удалена: {selected_del_group['name']}")
                        st.session_state.pop(confirm_key, None)
                        st.success("Группа удалена из базы")
                        st.rerun()
                    if st.button("Отмена", use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                else:
                    if st.button("🗑️ Удалить навсегда", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()

# ==================================================================
# ВКЛАДКА 2: СОЗДАНИЕ
# ==================================================================
with tab_create:
    st.subheader("➕ Новая группа (по заявке)")

    all_users_for_curator = db.get_all_users(include_inactive=False)
    curator_options = {
        "— не назначен —": None,
        **{
            f"{u['full_name'] or u['username']} ({u['username']})": u["id"]
            for u in all_users_for_curator
        },
    }

    with st.form("create_group_form", clear_on_submit=True):
        st.write("**Данные организации (Заказчика)**")
        c1, c2 = st.columns(2)
        with c1:
            g_name = st.text_input("Название группы (для системы) *", help="Например: П-21")
            org_name = st.text_input("Название организации (полное)")
            org_address = st.text_area("Юридический/Почтовый адрес", height=68)
        with c2:
            org_phone = st.text_input("Телефон")
            org_email = st.text_input("E-mail")
            manager_name = st.text_input("Руководитель организации (ФИО и должность)")

        st.write("**Контактные данные и параметры**")
        c3, c4 = st.columns(2)
        with c3:
            contact_person = st.text_input("Контактное лицо (ФИО)")
            g_curator_label = st.selectbox("Куратор (Методист)", list(curator_options.keys()))
        with c4:
            g_start = st.date_input("Дата начала")
            g_end = st.date_input("Дата окончания", value=None)

        submitted = st.form_submit_button("✅ Создать", type="primary")

        if submitted:
            if not g_name.strip():
                st.error("Укажите название группы")
            else:
                gid = db.create_group(
                    name=g_name.strip(),
                    description=f"Организация: {org_name}",
                    curator_id=curator_options[g_curator_label],
                    start_date=g_start, end_date=g_end,
                    created_by=USER
                )
                
                db.execute_query("""
                    UPDATE `groups` 
                    SET organization_name=%s, organization_address=%s, 
                        organization_phone=%s, organization_email=%s, 
                        contact_person=%s, manager_name=%s
                    WHERE id=%s
                """, (org_name, org_address, org_phone, org_email, contact_person, manager_name, gid), commit=True)

                db.log_action(USER_ID, "group_create", f"Создана группа: {g_name}")
                st.success(f"✅ Группа создана (ID: {gid})")
                st.rerun()

# ==================================================================
# ВКЛАДКА 3: СОСТАВ ГРУППЫ
# ==================================================================
with tab_members:
    st.subheader("👤 Состав группы")

    groups = db.get_all_groups(only_active=False)
    if not groups:
        st.info("Нет групп — создайте сначала группу")
        st.stop()

    group_map = {f"#{g['id']} — {g['name']} ({g['member_count']} чел.)": g for g in groups}
    selected_g_label = st.selectbox("Группа", list(group_map.keys()), key="gm_group")
    group = group_map[selected_g_label]

    st.caption(f"**Группа:** {group['name']} | Куратор: {group.get('curator_name') or '—'}")

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


# ==================================================================
# ВКЛАДКА 4: ОТЧЁТ ПО ГРУППЕ
# ==================================================================
with tab_report:
    st.subheader("📊 Отчёт по группе")

    groups = db.get_all_groups(only_active=False)
    if not groups:
        st.info("Нет групп")
        st.stop()

    group_map = {f"#{g['id']} — {g['name']}": g for g in groups}
    sel_label = st.selectbox("Группа", list(group_map.keys()), key="rep_group")
    group = group_map[sel_label]

    members = db.get_group_members(group["id"], only_active=True)

    topics = ["Все темы"] + db.get_all_topics(include_archived=True)
    topic_filter = st.selectbox("Тема", topics, key="rep_topic")
    topic_value = None if topic_filter == "Все темы" else topic_filter

    c1, c2 = st.columns(2)
    with c1:
        date_from = st.date_input("С", value=None, key="rep_from")
    with c2:
        date_to = st.date_input("По", value=None, key="rep_to")

    stats = db.get_group_statistics(group["id"], topic=topic_value)

    if not stats:
        st.info("Нет данных по группе")
    else:
        df_stats = build_group_report_dataframe(stats)

        if not df_stats.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Участников", len(df_stats))
            c2.metric("Всего тестов", int(df_stats["Тестов"].sum()))
            passed = df_stats[df_stats["Средний балл %"] >= 60]
            c3.metric("Сдали (≥60%)", f"{len(passed)} / {len(df_stats)}")
            avg = df_stats["Средний балл %"].mean()
            c4.metric("Средний балл группы", f"{avg:.1f}%")

        st.divider()
        st.dataframe(df_stats, use_container_width=True, hide_index=True)

        if not df_stats.empty:
            fig = px.bar(
                df_stats, x="ФИО", y="Средний балл %",
                text="Средний балл %", color="Средний балл %",
                color_continuous_scale="RdYlGn", range_color=[0, 100],
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("📄 Детальные результаты")

        date_from_val = datetime.combine(date_from, datetime.min.time()) if date_from else None
        date_to_val = datetime.combine(date_to, datetime.max.time()) if date_to else None

        detailed = db.get_group_results_detailed(
            group["id"], topic=topic_value,
            date_from=date_from_val, date_to=date_to_val,
        )

        if not detailed:
            st.info("Нет результатов за указанный период")
        else:
            df_det = build_protocol_dataframe(group["name"], topic_filter, detailed)
            st.dataframe(df_det, use_container_width=True, hide_index=True)

            st.subheader("👁️ Просмотр ответов")
            
            res_options = {
                f"{r['full_name'] or r['username']} — {r['topic']} ({r['date'].strftime('%d.%m %H:%M')})": r['id']
                for r in detailed
            }
            
            selected_res_label = st.selectbox("Выберите результат для просмотра", list(res_options.keys()))
            
            if st.button("👁️ Открыть ответы", type="primary"):
                show_answers_dialog(res_options[selected_res_label])

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_group = "".join(c if c.isalnum() or c in "-_" else "_" for c in group["name"])

            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "📥 Скачать CSV",
                    data=dataframe_to_csv_bytes(df_det),
                    file_name=f"report_{safe_group}_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with c2:
                protocol_bytes = generate_protocol_xlsx(
                    group=group, 
                    members=members,
                    detailed_results=detailed,
                    date_str=datetime.now().strftime("%d.%m.%Y")
                )
                
                st.download_button(
                    "📄 Скачать ПРОТОКОЛ (Excel)",
                    data=protocol_bytes,
                    file_name=f"protocol_{safe_group}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )

# ==================================================================
# ВКЛАДКА 5: ДОКУМЕНТЫ (ПРОТОКОЛЫ + PDF)
# ==================================================================
with tab_documents:
    st.subheader("📎 Документы группы")

    groups = db.get_all_groups(only_active=False)
    if not groups:
        st.info("Нет групп")
        st.stop()

    group_map = {f"#{g['id']} — {g['name']}": g for g in groups}
    sel = st.selectbox("Группа", list(group_map.keys()), key="doc_group")
    group = group_map[sel]

    with st.expander("📤 Загрузить новый PDF-документ", expanded=False):
        with st.form("upload_doc_form", clear_on_submit=True):
            doc_type = st.selectbox(
                "Тип документа", 
                ["Заявка на обучение", "Распоряжение", "Подписанный протокол", "Другое"]
            )
            uploaded_pdf = st.file_uploader("Выберите PDF файл", type=["pdf"])
            
            if st.form_submit_button("💾 Сохранить документ", type="primary"):
                if uploaded_pdf is not None:
                    group_dir = f"uploads/group_{group['id']}"
                    os.makedirs(group_dir, exist_ok=True)
                    
                    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in uploaded_pdf.name)
                    file_path = f"{group_dir}/{doc_type}_{safe_name}"
                    
                    with open(file_path, "wb") as f:
                        f.write(uploaded_pdf.getbuffer())
                    
                    db.add_group_document(group["id"], doc_type, uploaded_pdf.name, file_path, USER)
                    db.log_action(USER_ID, "doc_upload", f"Загружен документ '{doc_type}' для группы {group['name']}")
                    
                    st.success("✅ Документ загружен!")
                    st.rerun()
                else:
                    st.warning("Выберите файл")

    st.divider()

    st.write("### 📄 Загруженные PDF")
    docs = db.get_group_documents(group["id"])
    if not docs:
        st.info("К этой группе пока не прикреплено ни одного PDF-документа.")
    else:
        for d in docs:
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.write(f"**{d['doc_type']}**")
                st.caption(f"Файл: {d['file_name']} | Загружен: {d['uploaded_at'].strftime('%d.%m.%Y %H:%M')}")
            with c2:
                if os.path.exists(d['file_path']):
                    with open(d['file_path'], "rb") as f:
                        st.download_button(
                            "📥 Скачать",
                            data=f.read(),
                            file_name=d['file_name'],
                            mime="application/pdf",
                            key=f"dl_doc_{d['id']}"
                        )
                else:
                    st.error("Файл не найден")
            with c3:
                if st.button("🗑️", key=f"del_doc_{d['id']}", help="Удалить документ"):
                    if os.path.exists(d['file_path']):
                        os.remove(d['file_path'])
                    db.delete_group_document(d['id'])
                    db.log_action(USER_ID, "doc_delete", f"Удален документ '{d['doc_type']}' для группы {group['name']}")
                    st.success("Документ удален")
                    st.rerun()

    st.divider()

    st.write("### 📊 Сгенерированные протоколы")
    protocols = db.get_protocols_for_group(group["id"])

    if not protocols:
        st.info("Автоматические протоколы еще не создавались.")
    else:
        for p in protocols:
            c1, c2 = st.columns([4, 1])
            with c1:
                status = "Закрыт" if p["status"] == "closed" else "Открыт"
                st.write(f"**Протокол #{p['id']}** — {p['title'] or 'Без названия'}")
                st.caption(f"Статус: {status} | Начат: {p['started_at'].strftime('%d.%m.%Y %H:%M') if p.get('started_at') else '—'}")
            with c2:
                if p.get("file_path") and os.path.exists(p["file_path"]):
                    with open(p["file_path"], "rb") as f:
                        st.download_button(
                            "📥 Скачать",
                            data=f.read(),
                            file_name=os.path.basename(p["file_path"]),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_protocol_{p['id']}"
                        )
                else:
                    st.warning("Файл не найден")