"""📈 Дашборд методиста — сводная статистика."""
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.session import restore_session
from database import Database
from utils.auth import require_methodist

st.set_page_config(page_title="Дашборд", page_icon="📈", layout="wide")
restore_session()
require_methodist()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

st.title("📈 Дашборд методиста")
st.caption("Сводная статистика по обучению")

# ==================================================================
# 1. ОБЩИЕ МЕТРИКИ
# ==================================================================
# Получаем все данные
all_users = db.get_all_users(include_inactive=False)
all_groups = db.get_all_groups(only_active=True)
all_assignments = db.get_all_assignments()

# Считаем количество пройденных тестов (все результаты)
cursor = db.get_cursor()
cursor.execute("SELECT COUNT(*) as total_results FROM results")
total_results = cursor.fetchone()["total_results"]

# Считаем средний балл по всем тестам
cursor.execute("SELECT AVG(score * 100.0 / NULLIF(total_questions, 0)) as global_avg FROM results")
global_avg_row = cursor.fetchone()
global_avg = global_avg_row["global_avg"] or 0

# Считаем сдавших и не сдавших
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
# 2. ГРАФИК СДАЧИ (УСПЕВАЕМОСТЬ)
# ==================================================================
st.subheader("🎯 Успеваемость по заданиям")

if passed == 0 and failed == 0:
    st.info("Пока нет пройденных заданий для анализа.")
else:
    # Круговая диаграмма сдавших/не сдавших
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

st.divider()

# ==================================================================
# 3. АКТИВНОСТЬ ПО ГРУППАМ
# ==================================================================
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
            "Участников": g["member_count"],
            "Пройдено тестов": total_tests,
            "Средний балл %": round(avg_score, 1)
        })
    
    df_groups = pd.DataFrame(group_data)
    
    # Таблица групп
    st.dataframe(
        df_groups, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Средний балл %": st.column_config.ProgressColumn(
                "Средний балл %", min_value=0, max_value=100, format="%.1f%%"
            )
        }
    )
    
    # График по группам
    if not df_groups.empty:
        fig_bar = px.bar(
            df_groups, x="Группа", y="Пройдено тестов",
            text="Пройдено тестов", color="Средний балл %",
            color_continuous_scale="RdYlGn", range_color=[0, 100]
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ==================================================================
# 4. ПОСЛЕДНИЕ 10 РЕЗУЛЬТАТОВ
# ==================================================================
st.subheader("🕓 Последние результаты")
cursor.execute("""
    SELECT r.date, u.full_name, u.username, r.topic, r.score, r.total_questions,
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
        df_recent[["date", "full_name", "topic", "percentage"]],
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