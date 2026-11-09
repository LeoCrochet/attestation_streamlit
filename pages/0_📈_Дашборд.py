"""📈 Дашборд методиста — сводная статистика."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.session import restore_session
from database import Database
from utils.auth import require_methodist

st.set_page_config(page_title="Дашборд", page_icon="📈", layout="wide")
restore_session()
from utils.navigation import setup_page
setup_page()
require_methodist()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

st.title("📈 Дашборд методиста")
st.caption("Сводная статистика по обучению и качеству знаний")

# ==================================================================
# 1. ОБЩИЕ МЕТРИКИ
# ==================================================================
all_users = db.get_all_users(include_inactive=False)
all_groups = db.get_all_groups(only_active=True)
all_assignments = db.get_all_assignments()

cursor = db.get_cursor()
cursor.execute("SELECT COUNT(*) as total_results FROM results")
total_results = cursor.fetchone()["total_results"]

cursor.execute("SELECT AVG(score * 100.0 / NULLIF(total_questions, 0)) as global_avg FROM results")
global_avg_row = cursor.fetchone()
global_avg = global_avg_row["global_avg"] or 0

# Статистика сдачи (сдали / не сдали)
cursor.execute("""
    SELECT 
        SUM(CASE WHEN r.score * 100.0 / NULLIF(r.total_questions, 0) >= a.pass_score THEN 1 ELSE 0 END) as passed,
        SUM(CASE WHEN r.score * 100.0 / NULLIF(r.total_questions, 0) < a.pass_score THEN 1 ELSE 0 END) as failed
    FROM results r
    JOIN assignments a ON r.assignment_id = a.id
""")
pass_stats = cursor.fetchone()
passed = pass_stats["passed"] or 0
failed = pass_stats["failed"] or 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Всего пользователей", len(all_users))
c2.metric("Активных групп", len(all_groups))
c3.metric("Пройдено тестов", total_results)
c4.metric("Средний балл (общий)", f"{global_avg:.1f}%")

st.divider()

# ==================================================================
# 2. УСПЕВАЕМОСТЬ И АНАЛИТИКА
# ==================================================================
c1, c2 = st.columns(2)

# График успеваемости (Пончик)
with c1:
    st.subheader("🎯 Успеваемость по заданиям")
    if passed == 0 and failed == 0:
        st.info("Пока нет пройденных заданий для анализа.")
    else:
        df_status = pd.DataFrame({
            "Статус": ["Сдали", "Не сдали"],
            "Количество": [passed, failed]
        })
        fig_pie = px.pie(
            df_status, names="Статус", values="Количество", 
            hole=0.4, color="Статус",
            color_discrete_map={"Сдали": "#2ECC71", "Не сдали": "#E74C3C"}
        )
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)

# График по профессиям (Барчарт)
with c2:
    st.subheader("👷‍♂️ Качество знаний по профессиям")
    prof_stats = db.get_global_statistics_by_profession()
    if not prof_stats:
        st.info("Нет данных о профессиях сотрудников.")
    else:
        df_prof = pd.DataFrame(prof_stats)
        df_prof["avg_score"] = df_prof["avg_score"].round(1)
        
        fig_prof = px.bar(
            df_prof, x="profession", y="avg_score", text="avg_score",
            labels={"profession": "Профессия", "avg_score": "Средний балл %"},
            color="avg_score", color_continuous_scale="RdYlGn", range_color=[0, 100]
        )
        fig_prof.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_prof.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig_prof, use_container_width=True)

st.divider()

# ==================================================================
# 3. ДИНАМИКА ПО МЕСЯЦАМ
# ==================================================================
st.subheader("📅 Динамика сдачи тестов")
month_stats = db.get_global_statistics_by_month()

if not month_stats:
    st.info("Пока нет данных для построения динамики.")
else:
    df_month = pd.DataFrame(month_stats)
    df_month["avg_score"] = df_month["avg_score"].round(1)
    
    fig_month = px.line(
        df_month, x="month", y="total_tests", 
        markers=True, title="Количество сданных тестов по месяцам",
        labels={"month": "Месяц", "total_tests": "Количество тестов"}
    )
    fig_month.update_layout(height=300)
    st.plotly_chart(fig_month, use_container_width=True)

st.divider()

# ==================================================================
# 4. АКТИВНОСТЬ ГРУПП И ОТСТАЮЩИЕ
# ==================================================================
c1, c2 = st.columns(2)

with c1:
    st.subheader("👥 Активность групп")
    if not all_groups:
        st.info("Групп пока нет.")
    else:
        group_data = []
        for g in all_groups:
            stats = db.get_group_statistics(g["id"])
            total_tests = sum(s["tests_count"] or 0 for s in stats) if stats else 0
            avg_score = sum(s["avg_score"] or 0 for s in stats) / len(stats) if stats else 0
            
            group_data.append({
                "Группа": g["name"],
                "Тестов": total_tests,
                "Ср. балл %": round(avg_score, 1)
            })
        
        df_groups = pd.DataFrame(group_data)
        st.dataframe(
            df_groups, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Ср. балл %": st.column_config.ProgressColumn(
                    "Ср. балл %", min_value=0, max_value=100, format="%.1f%%"
                )
            }
        )

with c2:
    st.subheader("⚠️ Требуют внимания (Ср. балл < 60%)")
    cursor.execute("""
        SELECT 
            u.full_name, 
            AVG(r.score * 100.0 / NULLIF(r.total_questions, 0)) as avg_score
        FROM results r
        JOIN users u ON u.id = r.user_id
        GROUP BY u.id, u.full_name
        HAVING avg_score < 60
        ORDER BY avg_score ASC
        LIMIT 10
    """)
    lagging = cursor.fetchall()
    
    if not lagging:
        st.success("Отлично! Все пользователи имеют средний балл выше 60%.")
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
cursor.execute("""
    SELECT r.date, u.full_name, r.topic, 
           (r.score * 100.0 / NULLIF(r.total_questions, 0)) as percentage
    FROM results r
    JOIN users u ON u.id = r.user_id
    ORDER BY r.date DESC
    LIMIT 10
""")
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
            "percentage": st.column_config.NumberColumn("Результат", format="%d%%")
        }
    )
else:
    st.info("Результатов пока нет.")