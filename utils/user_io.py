"""Утилиты для работы с пользователями."""
import re
import secrets
import string


ROLES = ["user", "manager", "methodist", "admin"]
ROLE_LABELS = {
    "user": "👤 Пользователь",
    "manager": "🧑‍💼 Менеджер",
    "methodist": "👨‍🏫 Методист",
    "admin": "🔑 Администратор",
}


def generate_password(length=12):
    """Сгенерировать надёжный пароль."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def validate_username(username):
    """Проверить логин. Возвращает (ok, error)."""
    if not username or not username.strip():
        return False, "Логин не может быть пустым"
    username = username.strip()
    if len(username) < 3:
        return False, "Логин должен быть не короче 3 символов"
    if len(username) > 50:
        return False, "Логин не должен превышать 50 символов"
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        return False, "Логин может содержать только латиницу, цифры, _ . -"
    return True, None


def validate_email(email):
    """Проверить email (может быть пустым)."""
    if not email:
        return True, None
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "Некорректный email"
    return True, None


def validate_password(password, min_length=6):
    """Проверить пароль."""
    if not password:
        return False, "Пароль не может быть пустым"
    if len(password) < min_length:
        return False, f"Пароль должен быть не короче {min_length} символов"
    return True, None


def validate_full_name(full_name):
    """Проверить ФИО (может быть пустым)."""
    if full_name and len(full_name) > 100:
        return False, "ФИО не должно превышать 100 символов"
    return True, None


def role_label(role):
    """Человекочитаемое название роли."""
    return ROLE_LABELS.get(role, role)