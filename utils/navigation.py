"""Навигация, логин и общие настройки страниц."""
import streamlit as st
from database import Database
from utils.session import clear_session

NAV_ITEMS = [
    ("pages/0_📈_Дашборд.py",            "Дашборд",           "📈", {"methodist", "admin"}),
    ("pages/1_📝_Тестирование.py",        "Тестирование",      "📝", {"user", "manager", "methodist", "admin"}),
    ("pages/2_📊_Результаты.py",          "Результаты",        "📊", {"user", "manager", "methodist", "admin"}),
    ("pages/3_👤_Профиль.py",             "Профиль",           "👤", {"user", "manager", "methodist", "admin"}),
    ("pages/4_⚙️_Администрирование.py",   "Администрирование", "⚙️", {"admin"}),
    ("pages/5_👨‍🏫_Методист.py",           "Кабинет методиста", "👨‍🏫", {"methodist", "admin"}),
    ("pages/6_👥_Группы.py",              "Группы обучения",   "👥", {"methodist", "admin", "manager"}),
    ("pages/10_📌_Задания.py",            "Задания",           "📌", {"methodist", "admin"}), # <--- ДОБАВЛЕНО
    ("pages/7_📄_Мастер_заявок.py",       "Мастер заявок",     "📄", {"methodist", "admin"}),
    ("pages/8_🎯_Сурогат.py",             "Режим сурогата",    "🎯", {"methodist", "admin"}),
]

ROLE_LABELS = {
    "admin": "🔑 Администратор",
    "methodist": "👨‍🏫 Методист",
    "manager": "🧑‍💼 Менеджер",
    "user": "👤 Пользователь",
}


@st.cache_resource
def _get_db():
    return Database()


def _logout():
    clear_session()
    st.rerun()


def _render_login_form(db):
    """Форма входа в сайдбаре."""
    st.subheader("🔐 Вход")
    with st.form("login_form"):
        u = st.text_input("Логин")
        p = st.text_input("Пароль", type="password")
        if st.form_submit_button("Войти", use_container_width=True):
            user = db.authenticate_user(u, p)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user["username"]
                st.session_state.user_id = user["id"]
                st.session_state.role = user["role"]
                st.session_state.full_name = user["full_name"]
                st.query_params["user_id"] = str(user["id"])
                st.rerun()
            else:
                st.error("❌ Неверный логин или пароль")


def render_sidebar_auth():
    """Логин/выход + навигация в сайдбаре. Вызывать на каждой странице."""
    db = _get_db()

    with st.sidebar:
        st.title("🎓 Система аттестации")

        if st.session_state.get("authenticated"):
            st.write(f"👤 **{st.session_state.full_name or st.session_state.user}**")
            st.caption(ROLE_LABELS.get(st.session_state.role, st.session_state.role))
            st.divider()

            render_navigation()

            st.divider()
            if st.button("🚪 Выйти", use_container_width=True, key="logout_btn"):
                _logout()
        else:
            _render_login_form(db)


def setup_page():
    """Вызывать на каждой странице после set_page_config и restore_session."""
    # Прячем только авто-меню Streamlit (список pages/).
    # Нативную стрелку сворачивания (collapsedControl) НЕ трогаем.
    st.markdown("""
        <style>
            [data-testid="stSidebarNav"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    render_sidebar_auth()


def render_navigation():
    role = st.session_state.get("role")
    if not role:
        return
    
    # 1. Кнопка на главную страницу (Помощник)
    if st.button("🏠 Главная (Помощник)", use_container_width=True, key="nav_home"):
        st.switch_page("app.py")
        
    st.divider() # Визуальный разделитель

    # 2. Остальные разделы
    for path, label, icon, roles in NAV_ITEMS:
        if role not in roles:
            continue
        if st.button(f"{icon} {label}", use_container_width=True, key=f"nav_{path}"):
            st.switch_page(path)