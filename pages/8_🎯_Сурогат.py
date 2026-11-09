"""🎯 Режим сурогата: прохождение теста от имени сотрудника."""
import streamlit as st
from utils.session import restore_session
from utils.navigation import setup_page
from database import Database
from utils.auth import require_methodist

st.set_page_config(page_title="Сурогат", page_icon="🎯", layout="wide")
restore_session()
setup_page()
require_methodist()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

st.title("🎯 Режим сурогата")
st.caption("Пройдите тест от имени сотрудника (например, если у него нет доступа к компьютеру)")

# 1. Получаем список активных групп
groups = db.get_all_groups(only_active=True)

if not groups:
    st.warning("Нет активных групп обучения. Создайте группу и добавьте участников в разделе 👥 Группы.")
    st.stop()

group_map = {f"{g['name']} ({g['member_count']} чел.)": g for g in groups}
selected_group_label = st.selectbox("1. Выберите группу", list(group_map.keys()))
group = group_map[selected_group_label]

# 2. Получаем участников выбранной группы
members = db.get_group_members(group["id"], only_active=True)

if not members:
    st.info("В этой группе пока нет участников.")
    st.stop()

member_map = {
    f"{m['full_name'] or m['username']} ({m.get('profession') or 'без профессии'})": m 
    for m in members
}
selected_member_label = st.selectbox("2. Выберите сотрудника", list(member_map.keys()))
target_member = member_map[selected_member_label]

st.info(f"Вы собираетесь пройти тест от имени **{target_member['full_name'] or target_member['username']}**. Все результаты сохранятся в его профиль.")

# 3. Кнопка запуска
if st.button("📝 Начать тест за сотрудника", type="primary", use_container_width=True):
    st.session_state["impersonate_user_id"] = target_member["user_id"]
    st.session_state["impersonate_user_name"] = target_member["full_name"] or target_member["username"]
    st.session_state["impersonate_group_id"] = group["id"]
    
    # Очищаем возможные старые состояния теста
    for key in ("test_questions", "answers", "current_q", "test_finished", "test_start", "test_end_time", "is_free_test"):
        st.session_state.pop(key, None)
        
    st.switch_page("pages/1_📝_Тестирование.py")