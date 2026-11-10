"""📈 Дашборд методиста — сводная статистика."""
from datetime import datetime, date

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.session import restore_session
from utils.navigation import setup_page
from database import Database, EXCLUDED_ROLES
from utils.auth import require_methodist

st.set_page_config(page_title="Дашборд", page_icon="📈", layout="wide")
restore_session()
setup_page()
require_methodist()


@st.cache_resource
def get_db():
    return Database()


db = get_db()

st.title("📈 Дашборд методиста")
st.caption("Сводная статистика по обучению и качеству знаний")

# ==================================================================
# ФИЛЬТР ПО ПЕРИОДУ
# ==================================================================
with st.expander("🗓️ Фильтр по периоду", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        date_from = st.date_input("С", value=None, key="dash_from")
    with c2:
        date_to = st.date_input("По", value=None, key="dash_to")

date_from_val = datetime.combine(date_from, datetime.min.time()) if date_from else None
date_to_val = datetime.combine(date_to, datetime.max.time()) if date_to else None

# WHERE для results с учётом периода
def _results_where(alias="r"):
    where, params = ["1=1"], []
    if date_from_val:
        where.append(f"{alias}.date >= %s")
        params.append(date_from_val)
    if date_to_val:
        where.append(f"{alias}.date <= %s")
        params.append(date_to_val)
    return " AND ".join(where), params


# Фильтр по служебным ролям
role_placeholders = ", ".join(["%s"] * len(EXCLUDED_ROLES))
role_filter = f"u.role NOT IN ({role_placeholders})"
role_params = list(EXCLUDED_ROLES)

# ==================================================================
# 1. ОБЩИЕ МЕТРИКИ
# ==================================================================
all_users = db.get_all_users(include_inactive=False)
all_groups = db.get_all_groups(only_active=True)

cursor = db.get_cursor()
where_sql, params = _results_where()

cursor.execute(
    f"""
    SELECT COUNT(*) AS total_results
    FROM results r
    JOIN users u ON u.id = r.user_id
    WHERE {where_sql} AND {role_filter}
    """,
    params + role_params,
)
total_results = cursor.fetchone()["total_results"]

cursor.execute(
    f"""
    SELECT AVG(r.score * 100.0 / NULLIF(r.total_questions, 0)) AS global_avg
    FROM results r
    JOIN users u ON u.id = r.user_id
    WHERE {where_sql} AND {role_filter}
    """,
    params + role_params,
)
global_avg_row = cursor.fetchone()
global_avg = global_avg_row["global_avg"] or 0

cursor.execute(
    f"""
    SELECT
        SUM(CASE WHEN r.score * 100.0 / NULLIF(r.total_questions, 0) >= a.pass_score THEN 1 ELSE 0 END) AS passed,
        SUM(CASE WHEN r.score * 100.0 / NULLIF(r.total_questions, 0) < a.pass_score THEN 1 ELSE 0 END) AS failed
    FROM results r
    JOIN users u ON u.id = r.user_id
    JOIN assignments a ON r.assignment_id = a.id
    WHERE {where_sql} AND {role_filter}
    """,
    params + role_params,
)
pass_stats = cursor.fetchone()
passed = pass_stats["passed"] or 0
failed = pass_stats["failed"] or 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 Пользователей", len(all_users))
c2.metric("📚 Активных групп", len(all_groups))
c3.metric("📝 Пройдено тестов", total_results)
c4.metric("🎯 Средний балл", f"{global_avg:.1f}%")

st.divider()

# ==================================================================
# 1.5. АКТИВНЫЕ ЗАДАНИЯ (БЫСТРЫЙ ДОСТУП)
# ==================================================================
st.subheader("🔥 Активные задания")

# Получаем только открытые задания
active_assignments = db.get_all_assignments(status="open")

if not active_assignments:
    st.info("📌 Нет активных заданий. Создайте их в разделе «👨‍🏫 Методист -> 📌 Задания».")
else:
    # Выводим задания в виде карточек
    for a in active_assignments:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            
            with c1:
                st.markdown(f"**{a['title'] or 'Без названия'}**")
                st.caption(f"Группа: {a['group_name']} | Тема: {a['topic'] or 'Все'}")
                
            with c2:
                st.write(f"Вопросов: {a['num_questions']}")
                st.write(f"Проходной: {a['pass_score']}%")
                
            with c3:
                # Считаем прогресс сдачи
                total_students = a.get("total_students") or 1
                completed = a.get("completed_count") or 0
                progress_pct = int((completed / total_students) * 100)
                st.write(f"Сдали: {completed} из {total_students}")
                st.progress(progress_pct / 100, text=f"{progress_pct}%")
                
            with c4:
                # Кнопка перехода к составу группы
                if st.button("👤 Группа", key=f"dash_go_group_{a['id']}", use_container_width=True):
                    st.session_state["current_group_id"] = a["group_id"]
                    st.switch_page("pages/9_👤_Состав_группы.py")
                    
               # Кнопка перехода к деталям задания
                if st.button("📌 Задание", key=f"dash_go_assign_{a['id']}", use_container_width=True):
                    # Сохраняем ID в session_state и переходим
                    st.session_state["target_assignment_id"] = a["id"]
                    st.switch_page("pages/10_📌_Задания.py")
                    

st.divider()

# ==================================================================
# 2. УСПЕВАЕМОСТЬ И АНАЛИТИКА
# ==================================================================
c1, c2 = st.columns(2)

with c1:
    st.subheader("🎯 Успеваемость по заданиям")
    if passed == 0 and failed == 0:
        st.info("📊 Пока нет пройденных заданий. Как только сотрудники начнут сдавать тесты, здесь появится статистика.")
    else:
        df_status = pd.DataFrame({
            "Статус": ["Сдали", "Не сдали"],
            "Количество": [passed, failed],
        })
        fig_pie = px.pie(
            df_status, names="Статус", values="Количество",
            hole=0.4, color="Статус",
            color_discrete_map={"Сдали": "#2ECC71", "Не сдали": "#E74C3C"},
        )
        fig_pie.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("👷‍♂️ Качество знаний по профессиям")
    prof_stats = db.get_global_statistics_by_profession()
    if not prof_stats:
        st.info("👷‍♂️ Нет данных о профессиях. Убедитесь, что у сотрудников заполнено поле «Профессия» в группах.")
    else:
        df_prof = pd.DataFrame(prof_stats)
        df_prof["avg_score"] = df_prof["avg_score"].round(1)
        fig_prof = px.bar(
            df_prof, x="profession", y="avg_score", text="avg_score",
            labels={"profession": "Профессия", "avg_score": "Средний балл %"},
            color="avg_score", color_continuous_scale="RdYlGn", range_color=[0, 100],
        )
        fig_prof.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_prof.update_layout(
            height=350, 
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)'),
            xaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_prof, use_container_width=True)

st.divider()

# ==================================================================
# 3. ДИНАМИКА ПО МЕСЯЦАМ
# ==================================================================
st.subheader("📅 Динамика сдачи тестов")
month_stats = db.get_global_statistics_by_month()

if not month_stats:
    st.info("📅 Пока нет данных для построения динамики. Проведите несколько тестов, чтобы увидеть график.")
else:
    df_month = pd.DataFrame(month_stats)
    df_month["avg_score"] = df_month["avg_score"].round(1)
    fig_month = px.line(
        df_month, x="month", y="total_tests",
        markers=True, title="Количество сданных тестов по месяцам",
        labels={"month": "Месяц", "total_tests": "Количество тестов"},
    )
    fig_month.update_layout(
        height=300,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)'),
        xaxis=dict(showgrid=False)
    )
    st.plotly_chart(fig_month, use_container_width=True)

st.divider()

# ==================================================================
# 4. АКТИВНОСТЬ ГРУПП И ОТСТАЮЩИЕ
# ==================================================================
c1, c2 = st.columns(2)

with c1:
    st.subheader("👥 Активность групп")
    if not all_groups:
        st.info("👥 Групп пока нет. Создайте первую в разделе «👥 Группы обучения».")
    else:
        group_data = []
        for g in all_groups:
            stats = db.get_group_statistics(g["id"])
            total_tests = sum(s["tests_count"] or 0 for s in stats) if stats else 0
            avg_score = (
                sum(s["avg_score"] or 0 for s in stats) / len(stats)
                if stats else 0
            )
            group_data.append({
                "Группа": g["name"],
                "Тестов": total_tests,
                "Ср. балл %": round(avg_score, 1),
            })

        if not group_data:
            st.info("Нет данных по группам.")
        else:
            df_groups = pd.DataFrame(group_data)
            st.dataframe(
                df_groups,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ср. балл %": st.column_config.ProgressColumn(
                        "Ср. балл %", min_value=0, max_value=100, format="%.1f%%"
                    )
                },
            )

with c2:
    st.subheader("⚠️ Требуют внимания (Ср. балл < 60%)")
    cursor.execute(
        f"""
        SELECT u.full_name,
               AVG(r.score * 100.0 / NULLIF(r.total_questions, 0)) AS avg_score
        FROM results r
        JOIN users u ON u.id = r.user_id
        WHERE {where_sql} AND {role_filter}
        GROUP BY u.id, u.full_name
        HAVING avg_score < 60
        ORDER BY avg_score ASC
        LIMIT 10
        """,
        params + role_params,
    )
    lagging = cursor.fetchall()

    if not lagging:
        st.success("✅ Отлично! Все пользователи имеют средний балл выше 60%.")
    else:
        df_lag = pd.DataFrame(lagging)
        df_lag["avg_score"] = df_lag["avg_score"].round(1)
        df_lag.columns = ["ФИО", "Средний балл %"]
        st.dataframe(df_lag, use_container_width=True, hide_index=True)

st.divider()

# ==================================================================
# 5. ПОСЛЕДНИЕ 10 РЕЗУЛЬТАТОВ
# ==================================================================
st.subheader("🕓 Последние результаты")
cursor.execute(
    f"""
    SELECT r.date, u.full_name, r.topic,
           (r.score * 100.0 / NULLIF(r.total_questions, 0)) AS percentage
    FROM results r
    JOIN users u ON u.id = r.user_id
    WHERE {where_sql} AND {role_filter}
    ORDER BY r.date DESC
    LIMIT 10
    """,
    params + role_params,
)
recent = cursor.fetchall()

if recent:
    df_recent = pd.DataFrame(recent)
    df_recent["date"] = pd.to_datetime(df_recent["date"]).dt.strftime("%d.%m.%Y %H:%M")
    df_recent["percentage"] = df_recent["percentage"].round(1)
    st.dataframe(
        df_recent,
        use_container_width=True,
        hide_index=True,
        column_config={
            "date": "Дата",
            "full_name": "ФИО",
            "topic": "Тема",
            "percentage": st.column_config.NumberColumn("Результат", format="%d%%"),
        },
    )
else:
    st.info("🕓 Результатов пока нет.")