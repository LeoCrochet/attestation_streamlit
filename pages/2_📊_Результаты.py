import json
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

from utils.session import restore_session
from utils.navigation import setup_page
from database import Database, EXCLUDED_ROLES
from utils.auth import require_login
from utils.word_export import generate_answers_word

st.set_page_config(page_title="Результаты", page_icon="📊", layout="wide")

restore_session()
setup_page()
require_login()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

st.title("📊 Результаты")

# ==================================================================
# ДИАЛОГ ДЛЯ ПРОСМОТРА ДЕТАЛЕЙ (взят из 6_👥_Группы.py)
# ==================================================================
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
        st.warning("⚠️ Это старый формат ответов. Пройдите тест заново.")
        return

    for i, ans in enumerate(answers, start=1):
        st.markdown(f"### Вопрос {i}: {ans.get('question_text', '—')}")
        
        opts = ans.get("options", [])
        
        # Жесткая нормализация списков
        raw_user = ans.get("user_answer_idx")
        raw_correct = ans.get("correct_answer_idx")
        
        user_list = []
        if isinstance(raw_user, list):
            for x in raw_user: 
                if isinstance(x, list): user_list.extend(x)
                else: user_list.append(x)
        elif raw_user is not None:
            user_list = [raw_user]
            
        correct_list = []
        if isinstance(raw_correct, list):
            for x in raw_correct:
                if isinstance(x, list): correct_list.extend(x)
                else: correct_list.append(x)
        elif raw_correct is not None:
            correct_list = [raw_correct]

        # Выводим варианты через HTML
        for opt_i, opt_text in enumerate(opts):
            is_user = (opt_i in user_list)
            is_corr = (opt_i in correct_list)
            
            letter = chr(65 + opt_i)
            
            if is_user and is_corr:
                st.markdown(f"<div style='background-color: #d4edda; color: #155724; padding: 8px; border-radius: 5px; margin-bottom: 5px;'>✅ <b>{letter}. {opt_text}</b> <i>(Верно)</i></div>", unsafe_allow_html=True)
            elif is_corr:
                st.markdown(f"<div style='background-color: #cce5ff; color: #004085; padding: 8px; border-radius: 5px; margin-bottom: 5px;'>ℹ️ <b>{letter}. {opt_text}</b> <i>(Правильный ответ)</i></div>", unsafe_allow_html=True)
            elif is_user:
                st.markdown(f"<div style='background-color: #f8d7da; color: #721c24; padding: 8px; border-radius: 5px; margin-bottom: 5px;'>❌ <b>{letter}. {opt_text}</b> <i>(Выбрано неверно)</i></div>", unsafe_allow_html=True)
            else:
                st.write(f"▫️ {letter}. {opt_text}")
        
        st.divider()


# ==================================================================
# РАЗДЕЛЕНИЕ ПО РОЛЯМ
# ==================================================================
if st.session_state.get("role") in EXCLUDED_ROLES:
    # ==================================================================
    # ДЛЯ МЕТОДИСТА И АДМИНИСТРАТОРА: ТОЛЬКО РЕЗУЛЬТАТЫ ПОЛЬЗОВАТЕЛЕЙ
    # ==================================================================
    st.subheader("Результаты пользователей")
    
    cursor = db.get_cursor()
    role_placeholders = ", ".join(["%s"] * len(EXCLUDED_ROLES))
    cursor.execute(f"""
        SELECT r.id, r.date, u.full_name, u.username, u.role,
               r.topic, r.score, r.total_questions,
               (r.score * 100.0 / NULLIF(r.total_questions, 0)) AS percentage
        FROM results r
        JOIN users u ON u.id = r.user_id
        WHERE u.role NOT IN ({role_placeholders})
        ORDER BY r.date DESC
    """, list(EXCLUDED_ROLES))
    
    all_results = cursor.fetchall()
    
    if not all_results:
        st.info("Результатов пользователей пока нет.")
    else:
        df_all = pd.DataFrame(all_results)
        df_all["date"] = pd.to_datetime(df_all["date"])
        df_all["percentage"] = df_all["percentage"].round(1)

        # Фильтры
        c1, c2, c3 = st.columns(3)
        with c1:
            search = st.text_input("🔍 Поиск по ФИО или логину", key="res_search")
        with c2:
            topics = ["Все темы"] + sorted(df_all["topic"].unique().tolist())
            topic_filter = st.selectbox("Тема", topics, key="res_topic")
        with c3:
            date_range = st.date_input("Период", value=[], key="res_dates")
            
        # Применяем фильтры
        filtered = df_all.copy()
        if search:
            filtered = filtered[
                filtered["full_name"].str.contains(search, case=False, na=False) |
                filtered["username"].str.contains(search, case=False, na=False)
            ]
        if topic_filter != "Все темы":
            filtered = filtered[filtered["topic"] == topic_filter]
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered = filtered[
                (filtered["date"].dt.date >= start_date) & 
                (filtered["date"].dt.date <= end_date)
            ]

        if not filtered.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Всего тестов", len(filtered))
            c2.metric("Ср. балл", f"{filtered['percentage'].mean():.1f}%")
            c3.metric("Сдали (≥60%)", f"{(filtered['percentage'] >= 60).sum()} / {len(filtered)}")
            c4.metric("Уникальных сотрудников", filtered["username"].nunique())

            st.divider()
            display_all = filtered[["id", "date", "full_name", "topic", "score", "total_questions", "percentage"]].copy()
            display_all.columns = ["ID", "Дата", "ФИО", "Тема", "Правильно", "Всего", "Процент"]
            display_all["Дата"] = display_all["Дата"].dt.strftime("%d.%m.%Y %H:%M")
            
            st.dataframe(
                display_all,
                use_container_width=True,
                hide_index=True,
                column_config={"ID": None}
            )

            st.download_button(
                "📥 Скачать отфильтрованный CSV",
                data=display_all.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"all_results_{pd.Timestamp.now():%Y%m%d}.csv",
                mime="text/csv",
            )

            st.divider()
            st.subheader("👁️ Просмотр деталей ответов")
            
            res_options = {
                f"{r['full_name'] or r['username']} — {r['topic']} ({r['date'].strftime('%d.%m %H:%M')})": r['id']
                for r in filtered.to_dict("records")
            }
            
            selected_res = st.selectbox("Выберите результат для просмотра", list(res_options.keys()), key="admin_res_view")
            
            if st.button("👁️ Открыть ответы", type="primary"):
                show_answers_dialog(res_options[selected_res])
        else:
            st.warning("По заданным фильтрам ничего не найдено.")

else:
    # ==================================================================
    # ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ: МОИ РЕЗУЛЬТАТЫ
    # ==================================================================
    results = db.get_results(user_id=st.session_state.user_id)

    if not results:
        st.info("📭 У вас пока нет пройденных тестов")
    else:
        df = pd.DataFrame(results)
        df["percentage"] = (df["score"] / df["total_questions"] * 100).round(1)
        df["date"] = pd.to_datetime(df["date"])

        # Метрики
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Всего тестов", len(df))
        c2.metric("Средний балл", f"{df['percentage'].mean():.1f}%")
        c3.metric("Лучший результат", f"{df['percentage'].max():.1f}%")
        c4.metric("Всего правильных", int(df["score"].sum()))

        # График по темам
        by_topic = df.groupby("topic", as_index=False).agg(
            avg_score=("percentage", "mean"),
            tests=("percentage", "count"),
        )
        fig = px.bar(
            by_topic, x="topic", y="avg_score", text="avg_score",
            labels={"topic": "Тема", "avg_score": "Средний балл, %"},
            color="avg_score", color_continuous_scale="Viridis",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Таблица
        st.subheader("📋 История")
        display = df[["date", "topic", "score", "total_questions", "percentage"]].copy()
        display.columns = ["Дата", "Тема", "Правильно", "Всего", "Процент"]
        display["Дата"] = display["Дата"].dt.strftime("%d.%m.%Y %H:%M")
        st.dataframe(display, use_container_width=True, hide_index=True)

        # Экспорт
        st.download_button(
            "📥 Скачать CSV",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"results_{pd.Timestamp.now():%Y%m%d}.csv",
            mime="text/csv",
        )