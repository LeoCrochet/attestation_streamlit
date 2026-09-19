import pandas as pd
import plotly.express as px
import streamlit as st

from database import Database
from utils.auth import require_login

st.set_page_config(page_title="Результаты", page_icon="📊", layout="wide")
require_login()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

st.title("📊 Мои результаты")

results = db.get_results(user_id=st.session_state.user_id)

if not results:
    st.info("📭 У вас пока нет пройденных тестов")
    st.stop()

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