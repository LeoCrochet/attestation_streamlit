import os
import streamlit as st
from database import Database
from utils.session import restore_session
from utils.navigation import setup_page
from config import get_config

st.set_page_config(
    page_title="Система аттестации",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

restore_session()

@st.cache_resource
def get_db():
    return Database()

db = get_db()
cfg = get_config()

for key, default in [
    ("authenticated", False),
    ("user", None),
    ("user_id", None),
    ("role", None),
    ("full_name", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _read_readme() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "README.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "_README.md не найден._"


# Сайдбар (логин + навигация) + кнопка скрытия
setup_page()

# =========================================================
# ГЛАВНАЯ СТРАНИЦА = README.md
# =========================================================
st.caption(f"v{cfg.APP_VERSION}")

if st.session_state.authenticated:
    st.title(f"👋 Добро пожаловать, {st.session_state.full_name or st.session_state.user}!")
    st.caption("Краткая справка по системе — ниже. Разделы доступны в боковой панели 👈")
else:
    st.title("🎓 Система аттестации")
    st.info("Войдите в боковой панели, чтобы начать. Ниже — описание системы.")

st.divider()
st.markdown(_read_readme())