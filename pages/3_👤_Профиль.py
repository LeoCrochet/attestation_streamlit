import streamlit as st
from database import Database
from utils.auth import require_login

st.set_page_config(page_title="Профиль", page_icon="👤", layout="wide")
require_login()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

st.title("👤 Мой профиль")

user = db.get_user_by_id(st.session_state.user_id)
if not user:
    st.error("Пользователь не найден")
    st.stop()

st.write(f"**Логин:** `{user['username']}`")
st.write(f"**Полное имя:** {user['full_name'] or '—'}")
st.write(f"**Email:** {user['email'] or '—'}")
st.write(f"**Отдел:** {user['department'] or '—'}")
st.write(f"**Должность:** {user['position'] or '—'}")
st.write(f"**Роль:** {'🔑 Администратор' if user['role'] == 'admin' else '👤 Пользователь'}")
if user.get("created_at"):
    st.write(f"**Дата регистрации:** {user['created_at']}")
if user.get("last_login"):
    st.write(f"**Последний вход:** {user['last_login']}")

st.divider()
st.subheader("📊 Статистика")
stats = db.get_user_statistics(st.session_state.user_id)
if stats and stats.get("overall"):
    o = stats["overall"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего тестов", o["total_tests"] or 0)
    c2.metric("Средний балл", f"{o['avg_score'] or 0:.1f}%")
    c3.metric("Лучший результат", f"{o['max_score'] or 0:.1f}%")