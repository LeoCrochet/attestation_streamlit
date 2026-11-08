import streamlit as st
from database import Database

def restore_session():
    """
    Восстанавливает сессию из URL и принудительно удерживает user_id в адресной строке.
    """
    # Если мы уже авторизованы, но URL потерял параметр — возвращаем его
    if st.session_state.get("authenticated") and "user_id" not in st.query_params:
        st.query_params["user_id"] = str(st.session_state.user_id)

    # Если не авторизованы, но в URL есть user_id — восстанавливаем сессию
    if not st.session_state.get("authenticated") and "user_id" in st.query_params:
        try:
            uid = int(st.query_params["user_id"])
            db = Database()
            user = db.get_user_by_id(uid)
            if user:
                st.session_state.authenticated = True
                st.session_state.user = user["username"]
                st.session_state.user_id = user["id"]
                st.session_state.role = user["role"]
                st.session_state.full_name = user["full_name"]
        except Exception:
            pass

def save_session():
    """Сохраняет ID пользователя в URL (вызывать при логине)."""
    if st.session_state.get("user_id"):
        st.query_params["user_id"] = str(st.session_state.user_id)

def clear_session():
    """Очищает сессию и URL (вызывать при выходе)."""
    st.query_params.clear()
    for k in ("authenticated", "user", "user_id", "role", "full_name"):
        st.session_state.pop(k, None)