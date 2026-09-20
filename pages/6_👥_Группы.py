"""👥 Управление группами обучения и отчёты."""
from datetime import datetime, date

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
    st.subheader("➕ Новая группа")

    all_users_for_curator = db.get_all_users(include_inactive=False)
    curator_options = {
        "— не назначен —": None,
        **{
            f"{u['full_name'] or u['username']} ({u['username']})": u["id"]
            for u in all_users_for_curator
        },
    }

    with st.form("create_group_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            g_name = st.text_input("Название группы *", help="Например: П-21, Python-2026-01")
            g_desc = st.text_area("Описание", height=80)
        with c2:
            g_curator_label = st.selectbox("Куратор", list(curator_options.keys()))
            g_start = st.date_input("Дата начала", value=date.today())
            g_end = st.date_input("Дата окончания", value=None)

        submitted = st.form_submit_button("✅ Создать", type="primary")

        if submitted:
            if not g_name.strip():
                st.error("Укажите название группы")
            elif db.get_all_groups() and any(
                g["name"].lower() == g_name.strip().lower()
                for g in db.get_all_groups()
            ):
                st.error(f"Группа «{g_name}» уже существует")
            else:
                gid = db.create_group(
                    name=g_name.strip(),
                    description=g_desc.strip() or None,
                    curator_id=curator_options[g_curator_label],
                    start_date=g_start,
                    end_date=g_end,
                    created_by=USER,
                )
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

    if members:
        df_members = pd.DataFrame([
            {
                "ID": m["user_id"],
                "Логин": m["username"],
                "ФИО": m["full_name"] or "—",
                "Email": m["email"] or "—",
                "Роль в группе": m["role_in_group"],
                "В группе с": m["joined_at"].strftime("%d.%m.%Y") if m.get("joined_at") else "—",
            }
            for m in members
        ])
        st.dataframe(df_members, use_container_width=True, hide_index=True)

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

    st.divider()
    st.subheader("➕ Добавить участника")

    # Исключаем уже добавленных
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
        c1, c2 = st.columns([3, 1])
        with c1:
            add_labels = st.multiselect(
                "Выберите одного или несколько", list(add_map.keys()),
                key="gm_add_multi",
            )
        with c2:
            role_in_group = st.selectbox(
                "Роль в группе", ["student", "assistant", "curator"],
                key="gm_add_role",
            )

        if st.button("✅ Добавить", type="primary", key="gm_add_btn"):
            if not add_labels:
                st.warning("Выберите хотя бы одного пользователя")
            else:
                added = 0
                for lbl in add_labels:
                    db.add_group_member(group["id"], add_map[lbl], role_in_group)
                    added += 1
                db.log_action(USER_ID, "group_member_add",
                              f"Добавлено в {group['name']}: {added}")
                st.success(f"✅ Добавлено: {added}")
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