import streamlit as st
from database import Database
from utils.session import restore_session, clear_session

st.set_page_config(
    page_title="Система аттестации",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Восстанавливаем сессию (если обновили страницу)
restore_session()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

# 2. Инициализация полей сессии по умолчанию
for key, default in [
    ("authenticated", False),
    ("user", None),
    ("user_id", None),
    ("role", None),
    ("full_name", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def logout():
    """Выход из системы"""
    clear_session()
    st.rerun()


# =========================================================
# БОКОВАЯ ПАНЕЛЬ
# =========================================================
with st.sidebar:
    st.title("🎓 Система аттестации")
    st.divider()

    if st.session_state.authenticated:
        st.write(f"👤 **{st.session_state.full_name or st.session_state.user}**")
        
        role_label = "🔑 Администратор"
        if st.session_state.role == "methodist":
            role_label = "👨‍🏫 Методист"
        elif st.session_state.role == "user":
            role_label = "👤 Пользователь"
        elif st.session_state.role == "manager":
            role_label = "🧑‍💼 Менеджер"
            
        st.caption(role_label)
        st.divider()
        
        if st.button("🚪 Выйти", use_container_width=True):
            logout()
            
    else:
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
                    
                    # Сохраняем ID в URL
                    st.query_params["user_id"] = str(user["id"])
                    st.rerun()
                else:
                    st.error("❌ Неверный логин или пароль")


# =========================================================
# ГЛАВНАЯ СТРАНИЦА
# =========================================================
if st.session_state.authenticated:
    st.title(f"👋 Добро пожаловать, {st.session_state.full_name or st.session_state.user}!")
    st.info("Выберите раздел в боковой панели слева 👈")
else:
    st.title("🎓 Система аттестации")
    st.info("Войдите, чтобы начать")