"""👥 Управление группами обучения и отчёты."""
from datetime import datetime, date
import time
import random

import pandas as pd
import plotly.express as px
import streamlit as st

from database import Database
from utils.auth import require_login
from utils.protocol_io import (
    build_group_report_dataframe, build_protocol_dataframe,
    dataframe_to_csv_bytes, dataframe_to_excel_bytes,
)

st.set_page_config(page_title="Группы", page_icon="👥", layout="wide")
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

st.title("👥 Группы обучения")


tab_list, tab_create, tab_members, tab_report, tab_protocols = st.tabs([
    "📋 Список групп",
    "➕ Создать группу",
    "👤 Состав группы",
    "📊 Отчёт по группе",
    "📄 Протоколы",
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
                # Сохраняем группу
                gid = db.create_group(
                    name=g_name.strip(),
                    description=f"Организация: {org_name}",
                    curator_id=curator_options[g_curator_label],
                    start_date=g_start, end_date=g_end,
                    created_by=USER
                )
                
                # Дописываем данные организации (пока простым UPDATE)
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

        # --- БЛОК СУРОГАТА (Тест от имени сотрудника) ---
        st.divider()
        st.subheader("🎯 Пройти тест от имени сотрудника")
        st.write("Используйте эту функцию, если сотрудник не может пройти тест самостоятельно.")
        
        target_member = st.selectbox(
            "Выберите сотрудника", 
            options=members, 
            format_func=lambda m: f"{m['full_name'] or m['username']} ({m.get('profession') or 'без профессии'})",
            key="surrogate_target"
        )
        
        if st.button("📝 Начать тест за сотрудника", type="primary", key="btn_surrogate"):
            st.session_state["impersonate_user_id"] = target_member["user_id"]
            st.session_state["impersonate_user_name"] = target_member["full_name"] or target_member["username"]
            st.session_state["impersonate_group_id"] = group["id"]
            st.switch_page("pages/1_📝_Тестирование.py")

        # --- УДАЛЕНИЕ ИЗ ГРУППЫ ---
        st.divider()
        st.subheader("🚫 Удалить из группы")
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
        st.info("В группе пока нет участников")

    # --- ДОБАВЛЕНИЕ УЧАСТНИКА (ПО ОДНОМУ) ---
    st.divider()
    st.subheader("➕ Добавить одного участника вручную")

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

    # --- МАССОВЫЙ ИМПОРТ ИЗ ЗАЯВКИ (EXCEL/CSV) ---
    st.divider()
    st.subheader("📥 Импорт заявки (Excel/CSV)")
    st.write("Загрузите список сотрудников из заявки, и система автоматически создаст для них аккаунты и добавит в группу.")
    
    # Скачивание шаблона
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

    # Загрузка файла
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
                    
                    # Ищем пользователя по ФИО
                    all_db_users = db.get_all_users(include_inactive=True)
                    user = next((u for u in all_db_users if u["full_name"] and u["full_name"].strip().lower() == fio.strip().lower()), None)
                    
                    # Создаем, если нет
                    if not user:
                        username = f"student_{random.randint(10000, 99999)}"
                        default_password = "123456"
                        
                        user_id = db.create_user(
                            username=username,
                            password=default_password,
                            full_name=fio,
                            role="user"
                        )
                        created_count += 1
                    else:
                        user_id = user["id"]
                        
                    # Добавляем в группу
                    db.add_group_member(
                        group_id=group["id"],
                        user_id=user_id,
                        role_in_group="student",
                        profession=person["profession"],
                        education=person["education"],
                        birth_year=person["birth_year"],
                        training_type=person["training_type"]
                    )
                    added_count += 1
                
                db.log_action(USER_ID, "group_bulk_import", f"Импорт заявки в {group['name']}: {added_count} чел.")
                st.success(f"✅ Успешно добавлено: {added_count} чел. (Создано аккаунтов: {created_count})")
                time.sleep(1.5)
                st.rerun()


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

    # Тема
    topics = ["Все темы"] + db.get_all_topics(include_archived=True)
    topic_filter = st.selectbox("Тема", topics, key="rep_topic")
    topic_value = None if topic_filter == "Все темы" else topic_filter

    # Фильтр по дате
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

        # Метрики группы
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

        # График
        if not df_stats.empty:
            fig = px.bar(
                df_stats, x="ФИО", y="Средний балл %",
                text="Средний балл %",
                color="Средний балл %",
                color_continuous_scale="RdYlGn",
                range_color=[0, 100],
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Детальные результаты
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

            # Экспорт
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_group = "".join(c if c.isalnum() or c in "-_" else "_"
                                 for c in group["name"])

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
                header_info = {
                    "group": group["name"],
                    "topic": topic_filter,
                    "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                }
                try:
                    excel_bytes = dataframe_to_excel_bytes(
                        df_det, sheet_name="Отчёт", header_info=header_info,
                    )
                    st.download_button(
                        "📥 Скачать Excel",
                        data=excel_bytes,
                        file_name=f"report_{safe_group}_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Ошибка генерации Excel: {e}")


# ==================================================================
# ВКЛАДКА 5: ПРОТОКОЛЫ
# ==================================================================
with tab_protocols:
    st.subheader("📄 Протоколы тестирования")

    groups = db.get_all_groups(only_active=False)
    if not groups:
        st.info("Нет групп")
        st.stop()

    group_map = {f"#{g['id']} — {g['name']}": g for g in groups}
    sel = st.selectbox("Группа", list(group_map.keys()), key="prot_group")
    group = group_map[sel]

    protocols = db.get_protocols_for_group(group["id"])

    if protocols:
        df_p = pd.DataFrame([
            {
                "ID": p["id"],
                "Название": p["title"] or "—",
                "Тема": p["topic"] or "Все",
                "Статус": p["status"],
                "Начат": p["started_at"].strftime("%d.%m.%Y %H:%M") if p.get("started_at") else "—",
                "Закрыт": p["closed_at"].strftime("%d.%m.%Y %H:%M") if p.get("closed_at") else "—",
            }
            for p in protocols
        ])
        st.dataframe(df_p, use_container_width=True, hide_index=True)
    else:
        st.info("Протоколов пока нет")

    st.divider()
    st.subheader("➕ Создать протокол")

    with st.form("create_protocol_form", clear_on_submit=True):
        p_title = st.text_input("Название протокола", placeholder="Аттестация П-21, декабрь 2026")
        p_topic = st.text_input("Тема", placeholder="Python (оставьте пустым — все темы)")
        p_desc = st.text_area("Описание", height=80)

        if st.form_submit_button("✅ Создать протокол", type="primary"):
            pid = db.create_protocol(
                group_id=group["id"],
                topic=p_topic.strip() or None,
                title=p_title.strip() or None,
                description=p_desc.strip() or None,
                created_by=USER,
            )
            db.log_action(USER_ID, "protocol_create",
                          f"Протокол #{pid} для группы {group['name']}")
            st.success(f"✅ Протокол создан (ID: {pid})")
            st.rerun()