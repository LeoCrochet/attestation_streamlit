import json
import random
import time

import streamlit as st

from database import Database
from utils.auth import require_login

st.set_page_config(page_title="Тестирование", page_icon="📝", layout="wide")
require_login()


@st.cache_resource
def get_db():
    return Database()


db = get_db()


def _reset_test_state():
    """Полный сброс состояния теста."""
    for key in (
        "test_questions",
        "answers",
        "current_q",
        "test_start",
        "test_finished",
        "test_topic",
        "balloons_shown",
    ):
        st.session_state.pop(key, None)


st.title("📝 Тестирование")


# ========== ЭКРАН 1: ВЫБОР И СТАРТ ==========
if not st.session_state.get("test_questions"):
    topics = ["Все темы"] + db.get_all_topics()

    c1, c2 = st.columns([2, 1])
    with c1:
        selected_topic = st.selectbox("Тема", topics, key="sel_topic")
    with c2:
        num_questions = st.number_input(
            "Кол-во вопросов", min_value=1, max_value=50, value=10, key="sel_num",
        )

    if st.button("🚀 Начать тест", type="primary", use_container_width=True):
        topic_filter = None if selected_topic == "Все темы" else selected_topic
        questions = db.get_questions_by_topic(topic_filter)
        if not questions:
            st.warning("Нет вопросов по выбранной теме")
        else:
            random.shuffle(questions)
            _reset_test_state()
            st.session_state.test_questions = questions[:num_questions]
            st.session_state.current_q = 0
            st.session_state.answers = {}
            st.session_state.test_start = time.time()
            st.session_state.test_topic = selected_topic
            st.session_state.test_finished = False
            st.rerun()


# ========== ЭКРАН 2: ПРОХОЖДЕНИЕ ТЕСТА ==========
elif not st.session_state.get("test_finished"):
    qs = st.session_state.test_questions
    idx = st.session_state.current_q
    q = qs[idx]

    st.progress(idx / len(qs), text=f"Вопрос {idx + 1} из {len(qs)}")
    st.subheader(q["question"])

    options = json.loads(q["options"])
    labels = [f"{chr(65 + i)}. {o}" for i, o in enumerate(options)]

    choice = st.radio("Вариант ответа", labels, key=f"radio_{idx}")
    selected_idx = labels.index(choice)

    c1, c2 = st.columns([1, 1])
    with c1:
        if idx > 0 and st.button("⬅️ Назад", use_container_width=True):
            st.session_state.current_q -= 1
            st.rerun()
    with c2:
        btn_label = "Завершить ✅" if idx == len(qs) - 1 else "Далее ➡️"
        if st.button(btn_label, type="primary", use_container_width=True):
            st.session_state.answers[idx] = selected_idx

            if idx == len(qs) - 1:
                score = sum(
                    1 for i, qq in enumerate(qs)
                    if st.session_state.answers.get(i) == qq["correct_answer"]
                )
                db.save_result(
                    user_id=st.session_state.user_id,
                    user_name=st.session_state.user,
                    topic=st.session_state.get("test_topic", "Все"),
                    answers=st.session_state.answers,
                    score=score,
                    total=len(qs),
                    time_spent=int(time.time() - st.session_state.test_start),
                )
                st.session_state.test_finished = True
                st.session_state.balloons_shown = False  # покажем один раз
                st.rerun()
            else:
                st.session_state.current_q += 1
                st.rerun()


# ========== ЭКРАН 3: РЕЗУЛЬТАТЫ ==========
else:
    qs = st.session_state.test_questions
    ans = st.session_state.answers
    score = sum(1 for i, q in enumerate(qs) if ans.get(i) == q["correct_answer"])
    pct = score / len(qs) * 100

    # Шарики — один раз
    if not st.session_state.get("balloons_shown"):
        st.balloons()
        st.session_state.balloons_shown = True

    st.success(f"### Результат: {score} из {len(qs)} ({pct:.1f}%)")

    if pct >= 80:
        st.success("🎉 Отлично! Высокий уровень знаний.")
    elif pct >= 60:
        st.info("👍 Хороший результат.")
    else:
        st.warning("📚 Стоит повторить материал.")

    # Кнопки после результата
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ Закрыть", type="primary", use_container_width=True):
            _reset_test_state()
            st.rerun()
    with c2:
        if st.button("📊 Мои результаты", use_container_width=True):
            st.switch_page("pages/2_📊_Результаты.py")

    # Детали
    with st.expander("📋 Детальный просмотр ответов"):
        for i, q in enumerate(qs):
            options = json.loads(q["options"])
            user_idx = ans.get(i)
            user_text = options[user_idx] if user_idx is not None else "—"
            correct_text = options[q["correct_answer"]]
            is_correct = user_idx == q["correct_answer"]

            if is_correct:
                st.success(f"✅ {i + 1}. {q['question']}")
            else:
                st.error(f"❌ {i + 1}. {q['question']}")
                st.write(f"Ваш ответ: **{user_text}**")
                st.write(f"Правильный: **{correct_text}**")
            st.divider()