"""⚙️ Администрирование: управление пользователями."""
import streamlit as st
import pandas as pd

from database import Database
from utils.user_io import (
    ROLES, role_label,
    generate_password, validate_username, validate_email,
    validate_password, validate_full_name,
)

st.set_page_config(page_title="Администрирование", page_icon="⚙️", layout="wide")


# --- Проверка прав ---
if not st.session_state.get("authenticated"):
    st.warning("⚠️ Войдите в систему")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("⛔ Доступ только для администратора")
    st.stop()


# --- Подключение к БД ---
@st.cache_resource
def get_db():
    return Database()


db = get_db()

st.title("⚙️ Администрирование")
st.caption("Управление пользователями системы")


# ==================================================================
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ
# ==================================================================
with st.expander("➕ Создать пользователя", expanded=False):
    with st.form("create_user_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            u_username = st.text_input("Логин *", help="Латиница, цифры, _ . -")
            u_full_name = st.text_input("ФИО")
            u_email = st.text_input("Email")
        with c2:
            u_password = st.text_input(
                "Пароль *", type="password", help="Минимум 6 символов",
            )
            u_role = st.selectbox(
                "Роль", options=ROLES, format_func=role_label, index=0,
            )
            u_dept = st.text_input("Отдел")
            u_pos = st.text_input("Должность")

        c_gen, _ = st.columns([1, 3])
        with c_gen:
            gen_pwd_clicked = st.form_submit_button("🎲 Сгенерировать пароль")

        if gen_pwd_clicked:
            st.session_state["_gen_pwd"] = generate_password(12)

        if st.session_state.get("_gen_pwd"):
            st.code(st.session_state["_gen_pwd"], language=None)
            st.caption("Скопируйте пароль и передайте пользователю.")

        submitted = st.form_submit_button("✅ Создать", type="primary")

        if submitted:
            pwd = st.session_state.get("_gen_pwd") or u_password

            errors = []
            ok, err = validate_username(u_username)
            if not ok:
                errors.append(err)
            ok, err = validate_email(u_email)
            if not ok:
                errors.append(err)
            ok, err = validate_password(pwd)
            if not ok:
                errors.append(err)
            ok, err = validate_full_name(u_full_name)
            if not ok:
                errors.append(err)

            if not errors and db.get_user_by_username(u_username.strip()):
                errors.append(f"Пользователь «{u_username}» уже существует")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    db.create_user(
                        username=u_username.strip(),
                        password=pwd,
                        email=u_email.strip() or None,
                        full_name=u_full_name.strip() or None,
                        role=u_role,
                        department=u_dept.strip() or None,
                        position=u_pos.strip() or None,
                    )
                    db.log_action(
                        st.session_state.user_id,
                        "user_create",
                        f"Создан пользователь: {u_username}",
                    )
                    st.success(f"✅ Пользователь «{u_username}» создан")
                    st.session_state.pop("_gen_pwd", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка создания: {e}")


# ==================================================================
# ФИЛЬТРЫ
# ==================================================================
st.divider()
st.subheader("📋 Список пользователей")

c1, c2, c3 = st.columns([2, 2, 3])
with c1:
    f_role = st.selectbox(
        "Роль", ["Все"] + ROLES,
        format_func=lambda r: "Все" if r == "Все" else role_label(r),
    )
with c2:
    f_status = st.selectbox(
        "Статус", ["Все", "Только активные", "Только отключённые"],
    )
with c3:
    f_search = st.text_input("Поиск (логин, ФИО, email)")


# ==================================================================
# ЗАГРУЗКА
# ==================================================================
all_users = db.get_all_users(include_inactive=True)


def _match(u):
    if f_role != "Все" and u["role"] != f_role:
        return False
    if f_status == "Только активные" and not u["is_active"]:
        return False
    if f_status == "Только отключённые" and u["is_active"]:
        return False
    if f_search:
        s = f_search.lower()
        haystack = " ".join([
            u["username"] or "",
            u["full_name"] or "",
            u["email"] or "",
        ]).lower()
        if s not in haystack:
            return False
    return True


users = [u for u in all_users if _match(u)]
st.caption(f"Найдено: **{len(users)}** из {len(all_users)}")


# ==================================================================
# ТАБЛИЦА
# ==================================================================
if not users:
    st.info("Нет пользователей по заданным фильтрам")
else:
    df_users = pd.DataFrame([
        {
            "ID": u["id"],
            "Логин": u["username"],
            "ФИО": u["full_name"] or "—",
            "Email": u["email"] or "—",
            "Роль": role_label(u["role"]),
            "Отдел": u["department"] or "—",
            "Должность": u["position"] or "—",
            "Активен": "✅" if u["is_active"] else "🚫",
            "Последний вход": (
                u["last_login"].strftime("%d.%m.%Y %H:%M")
                if u["last_login"] else "—"
            ),
            "Создан": (
                u["created_at"].strftime("%d.%m.%Y")
                if u["created_at"] else "—"
            ),
        }
        for u in users
    ])

    st.dataframe(df_users, use_container_width=True, hide_index=True, height=400)


# ==================================================================
# ДЕЙСТВИЯ
# ==================================================================
if users:
    st.divider()
    st.subheader("🔧 Управление пользователем")

    user_options = {
        f"#{u['id']} — {u['username']} ({u['full_name'] or 'без имени'})": u
        for u in users
    }
    selected_label = st.selectbox("Выберите пользователя", list(user_options.keys()))
    selected = user_options[selected_label]
    is_self = selected["id"] == st.session_state.user_id

    # Статистика
    user_stats = db.get_user_statistics(selected["id"])
    if user_stats and user_stats.get("overall"):
        o = user_stats["overall"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Пройдено тестов", o.get("total_tests") or 0)
        c2.metric("Средний балл", f"{(o.get('avg_score') or 0):.1f}%")
        c3.metric("Лучший результат", f"{(o.get('max_score') or 0):.1f}%")

    # Редактирование
    with st.form(f"edit_user_{selected['id']}"):
        st.write(f"**Редактирование: `{selected['username']}`**")

        c1, c2 = st.columns(2)
        with c1:
            e_email = st.text_input("Email", value=selected["email"] or "")
            e_full_name = st.text_input("ФИО", value=selected["full_name"] or "")
            e_dept = st.text_input("Отдел", value=selected["department"] or "")
        with c2:
            e_pos = st.text_input("Должность", value=selected["position"] or "")
            e_role = st.selectbox(
                "Роль", options=ROLES, format_func=role_label,
                index=ROLES.index(selected["role"]) if selected["role"] in ROLES else 0,
                disabled=is_self,
            )
            e_active = st.checkbox(
                "Активен", value=bool(selected["is_active"]), disabled=is_self,
            )

        st.write("**Сброс пароля** (оставьте пустым, чтобы не менять)")
        new_pwd = st.text_input(
            "Новый пароль", type="password", key=f"pwd_{selected['id']}",
        )

        save = st.form_submit_button("💾 Сохранить", type="primary")

        if save:
            errors = []
            ok, err = validate_email(e_email)
            if not ok:
                errors.append(err)
            ok, err = validate_full_name(e_full_name)
            if not ok:
                errors.append(err)
            if new_pwd:
                ok, err = validate_password(new_pwd)
                if not ok:
                    errors.append(err)

            if errors:
                for e in errors:
                    st.error(e)
            else:
                fields = {
                    "email": e_email.strip() or None,
                    "full_name": e_full_name.strip() or None,
                    "department": e_dept.strip() or None,
                    "position": e_pos.strip() or None,
                    "is_active": e_active,
                }
                if not is_self:
                    fields["role"] = e_role
                if new_pwd:
                    fields["password"] = new_pwd

                try:
                    db.update_user(selected["id"], **fields)
                    db.log_action(
                        st.session_state.user_id,
                        "user_update",
                        f"Обновлён пользователь: {selected['username']}",
                    )
                    st.success("✅ Сохранено")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")

    # Деактивация
    if not is_self and selected["is_active"]:
        st.divider()
        confirm_key = f"confirm_deactivate_{selected['id']}"
        if st.session_state.get(confirm_key):
            st.warning(
                f"⚠️ Точно деактивировать **{selected['username']}**? "
                "Он не сможет войти."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("❌ Да, деактивировать", type="primary",
                             use_container_width=True):
                    db.deactivate_user(selected["id"])
                    db.log_action(
                        st.session_state.user_id,
                        "user_deactivate",
                        f"Деактивирован: {selected['username']}",
                    )
                    st.session_state.pop(confirm_key, None)
                    st.success("Пользователь деактивирован")
                    st.rerun()
            with c2:
                if st.button("Отмена", use_container_width=True):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
        else:
            if st.button("🚫 Деактивировать пользователя",
                         use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()

    if is_self:
        st.info("ℹ️ Вы редактируете свою учётную запись. Роль и статус изменить нельзя.")