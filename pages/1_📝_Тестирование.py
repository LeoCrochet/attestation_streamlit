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


# =========================================================
# 🥷 БЛОК СУРОГАТА (Прохождение теста за сотрудника)
# =========================================================
if "impersonate_user_id" in st.session_state:
    # Сохраняем данные методиста, чтобы вернуть их потом
    if "real_user_id" not in st.session_state:
        st.session_state.real_user_id = st.session_state.user_id
        st.session_state.real_user = st.session_state.user
        st.session_state.real_full_name = st.session_state.full_name

    # Подменяем личность на студента
    st.session_state.user_id = st.session_state.impersonate_user_id
    st.session_state.user = st.session_state.impersonate_user_name
    st.session_state.full_name = st.session_state.impersonate_user_name

    # Предупреждение для методиста
    st.warning(f"👨‍🏫 **Режим Методиста:** Вы проходите тест от имени сотрудника **{st.session_state.full_name}**.")
    
    if st.button("❌ Выйти из режима сурогата (вернуться к группам)"):
        # Возвращаем всё как было
        st.session_state.user_id = st.session_state.pop("real_user_id")
        st.session_state.user = st.session_state.pop("real_user")
        st.session_state.full_name = st.session_state.pop("real_full_name")
        
        del st.session_state["impersonate_user_id"]
        del st.session_state["impersonate_user_name"]
        if "impersonate_group_id" in st.session_state:
            del st.session_state["impersonate_group_id"]
            
        # Сбрасываем тест, если он шел
        for key in ("test_questions", "answers", "current_q", "test_finished", "test_start"):
            st.session_state.pop(key, None)
            
        st.switch_page("pages/6_👥_Группы.py")


def _reset_test_state():
    for key in (
        "test_questions",
        "answers",
        "current_q",
        "test_start",
        "test_finished",
        "test_topic",
        "balloons_shown",
        "assignment_id",
        "assignment_time_limit",
    ):
        st.session_state.pop(key, None)


st.title("📝 Тестирование")


# ========== АКТИВНЫЕ ЗАДАНИЯ ==========
# Загружаем задания для того пользователя, от чьего имени мы сейчас работаем
if not st.session_state.get("test_questions"):
    user_assignments = db.get_user_assignments(st.session_state.user_id, only_active=True)
    if user_assignments:
        st.subheader("📌 Активные задания")
        for a in user_assignments:
            attempts_left = a["max_attempts"] - (a["attempts_used"] or 0)
            is_done = (a.get("best_score") or 0) >= a["pass_score"]
            deadline_str = (a["due_date"].strftime("%d.%m.%Y %H:%M")
                            if a.get("due_date") else "без дедлайна")

            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    title = a["title"] or f"Тест по {a['topic'] or 'всем темам'}"
                    st.markdown(f"**{title}**")
                    st.caption(
                        f"Группа: {a['group_name']} • Тема: {a['topic'] or 'Все'} • "
                        f"Вопросов: {a['num_questions']} • Проходной: {a['pass_score']}% • "
                        f"Дедлайн: {deadline_str}"
                    )
                with c2:
                    if is_done:
                        st.success(f"✅ {a['best_score']:.0f}%")
                    elif attempts_left <= 0:
                        st.error("Попытки исчерпаны")
                    else:
                        st.info(f"Попыток: {attempts_left}")
                with c3:
                    disabled = is_done or attempts_left <= 0
                    if st.button("▶️ Начать", key=f"start_assign_{a['id']}",
                                 type="primary", use_container_width=True,
                                 disabled=disabled):
                        topic_filter = a["topic"]
                        questions = db.get_questions_by_topic(topic_filter)
                        if not questions:
                            st.error("Нет вопросов по теме")
                        else:
                            random.shuffle(questions)
                            _reset_test_state()
                            st.session_state.test_questions = questions[:a["num_questions"]]
                            st.session_state.current_q = 0
                            st.session_state.answers = {}
                            st.session_state.test_start = time.time()
                            st.session_state.test_topic = topic_filter or "Все"
                            st.session_state.test_finished = False
                            st.session_state.assignment_id = a["id"]
                            st.session_state.assignment_time_limit = a.get("time_limit_min")
                            st.rerun()
        st.divider()

# ========== ЭКРАН 1: ВЫБОР И СТАРТ (Свободный тест) ==========
if not st.session_state.get("test_questions"):
    topics = ["Все темы"] + db.get_all_topics()

    c1, c2 = st.columns([2, 1])
    with c1:
        selected_topic = st.selectbox("Тема", topics, key="sel_topic")
    with c2:
        num_questions = st.number_input(
            "Кол-во вопросов", min_value=1, max_value=50, value=10, key="sel_num",
        )

    if st.button("🚀 Начать тест (Свободный)", type="primary", use_container_width=True):
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

    options = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
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

                assignment_id = st.session_state.get("assignment_id")
                
                # Если это тест по заданию
                if assignment_id:
                    assignment = db.get_assignment(assignment_id)
                    group_id = assignment["group_id"] if assignment else None
                
                # Если это тест в режиме сурогата
                elif "impersonate_group_id" in st.session_state:
                    group_id = st.session_state["impersonate_group_id"]
                
                # Обычный свободный тест
                else:
                    user_groups = db.get_user_groups(st.session_state.user_id)
                    group_id = user_groups[0]["id"] if len(user_groups) == 1 else None

                db.save_result(
                    user_id=st.session_state.user_id,
                    user_name=st.session_state.user,
                    topic=st.session_state.get("test_topic", "Все"),
                    answers=st.session_state.answers,
                    score=score,
                    total=len(qs),
                    time_spent=int(time.time() - st.session_state.test_start),
                    group_id=group_id,
                    assignment_id=assignment_id,
                )
                st.session_state.test_finished = True
                st.session_state.balloons_shown = False
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

    if not st.session_state.get("balloons_shown"):
        st.balloons()
        st.session_state.balloons_shown = True

    st.success(f"### Результат: {score} из {len(qs)} ({pct:.1f}%)")

    if st.session_state.get("assignment_id"):
        assignment = db.get_assignment(st.session_state["assignment_id"])
        if assignment:
            passed = pct >= assignment["pass_score"]
            if passed:
                st.success(f"✅ Задание сдано (проходной {assignment['pass_score']}%)")
            else:
                st.warning(
                    f"⚠️ Не пройден проходной балл ({assignment['pass_score']}%). "
                    f"Осталось попыток: "
                    f"{max(0, assignment['max_attempts'] - 1)}"
                )
                
    if pct >= 80:
        st.success("🎉 Отлично! Высокий уровень знаний.")
    elif pct >= 60:
        st.info("👍 Хороший результат.")
    else:
        st.warning("📚 Стоит повторить материал.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ Закрыть", type="primary", use_container_width=True):
            _reset_test_state()
            st.rerun()
    with c2:
        if st.button("📊 Мои результаты", use_container_width=True):
            st.switch_page("pages/2_📊_Результаты.py")

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