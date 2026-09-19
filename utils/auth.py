"""Общие проверки авторизации для страниц."""
import streamlit as st


def require_login():
    if not st.session_state.get("authenticated"):
        st.warning("⚠️ Войдите в систему, чтобы получить доступ к этой странице")
        st.stop()


def require_admin():
    require_login()
    if st.session_state.get("role") != "admin":
        st.error("⛔ Доступ только для администратора")
        st.stop()


def current_user():
    return {
        "id": st.session_state.get("user_id"),
        "username": st.session_state.get("user"),
        "full_name": st.session_state.get("full_name"),
        "role": st.session_state.get("role"),
    }