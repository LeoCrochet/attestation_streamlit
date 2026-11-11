import json
import random
import time
import os
from datetime import datetime

from utils.session import restore_session
from utils.navigation import setup_page
import streamlit as st

from database import Database
from utils.auth import require_login

st.set_page_config(page_title="Тестирование", page_icon="📝", layout="wide")

restore_session()
setup_page()
require_login()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

# =========================================================
# 🥷 БЛОК СУРОГАТА
# =========================================================
if "impersonate_user_id" in st.session_state:
    if "real_user_id" not in st.session_state:
        st.session_state.real_user_id = st.session_state.user_id
        st.session_state.real_user = st.session_state.user
        st.session_state.real_full_name = st.session_state.full_name

    st.session_state.user_id = st.session_state.impersonate_user_id
    st.session_state.user = st.session_state.impersonate_user_name
    st.session_state.full_name = st.session_state.impersonate_user_name

    st.warning(f"👨‍🏫 **Режим Методиста:** Вы проходите тест от имени сотрудника **{st.session_state.full_name}**.")
    
    if st.button("❌ Выйти из режима сурогата (вернуться к группам)"):
        st.session_state.user_id = st.session_state.pop("real_user_id")
        st.session_state.user = st.session_state.pop("real_user")
        st.session_state.full_name = st.session_state.pop("real_full_name")
        
        del st.session_state["impersonate_user_id"]
        del st.session_state["impersonate_user_name"]
        if "impersonate_group_id" in st.session_state:
            del st.session_state["impersonate_group_id"]
            
        for key in ("test_questions", "answers", "current_q", "test_finished", "test_start", "test_end_time"):
            st.session_state.pop(key, None)
            
        st.switch_page("pages/6_👥_Группы.py")


def _reset_test_state():
    for key in (
        "test_questions", "answers", "current_q", "test_start", "test_finished",
        "test_topic", "balloons_shown", "assignment_id", "assignment_time_limit", "test_end_time",
        "result_saved", "is_free_test"
    ):
        st.session_state.pop(key, None)

def _flatten(lst):
    """Убирает вложенность списков (например, [[0, 1]] -> [0, 1])."""
    res = []
    for item in lst:
        if isinstance(item, list):
            res.extend(_flatten(item))
        else:
            res.append(item)
    return res


st.title("📝 Тестирование")

# ========== АКТИВНЫЕ ЗАДАНИЯ ==========
if not st.session_state.get("test_questions"):
    user_assignments = db.get_user_assignments(st.session_state.user_id, only_active=True)
    if user_assignments:
        st.subheader("📌 Активные задания")
        for a in user_assignments:
            attempts_left = a["max_attempts"] - (a["attempts_used"] or 0)
            is_done = (a.get("best_score") or 0) >= a["pass_score"]
            
            deadline_str = "без дедлайна"
            deadline_color = "gray"
            if a.get("due_date"):
                now = datetime.now()
                due = a["due_date"]
                delta = due - now
                deadline_str = due.strftime("%d.%m.%Y %H:%M")
                if delta.total_seconds() < 0:
                    deadline_color = "red"
                    deadline_str += " (просрочено)"
                elif delta.total_seconds() < 86400:
                    deadline_color = "orange"

            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{a['title'] or a['topic'] or 'Все темы'}**")
                    st.caption(f"Группа: {a['group_name']} • Вопросов: {a['num_questions']} • Проходной: {a['pass_score']}%")
                    if a.get("is_training"):
                        st.caption("🎓 **Тренировка:** результаты не сохраняются в статистику.")
                    st.markdown(f"Дедлайн: :{deadline_color}[{deadline_str}]", unsafe_allow_html=True)
                with c2:
                    if is_done:
                        st.success(f"✅ {a['best_score']:.0f}%")
                    elif attempts_left <= 0:
                        st.error("Попытки исчерпаны")
                    else:
                        st.info(f"Попыток: {attempts_left} из {a['max_attempts']}")
                        st.progress((a["max_attempts"] - attempts_left) / a["max_attempts"], text=f"Использовано {a['max_attempts'] - attempts_left}")
                with c3:
                    disabled = is_done or attempts_left <= 0
                    if st.button("▶️ Начать", key=f"start_assign_{a['id']}", type="primary", use_container_width=True, disabled=disabled):
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
                            
                            time_limit = a.get("time_limit_min")
                            if time_limit and time_limit > 0:
                                st.session_state.test_end_time = time.time() + (time_limit * 60)
                            st.rerun()
        st.divider()

# ========== ЭКРАН 1: ВЫБОР И СТАРТ ==========
if not st.session_state.get("test_questions"):
    if st.session_state.get("role") in ("admin", "methodist"):
        st.info("💡 Режим проверки: вы можете пройти свободный тест, чтобы проверить работу системы.")
        topics = ["Все темы"] + db.get_all_topics()

        c1, c2 = st.columns([2, 1])
        with c1:
            selected_topic = st.selectbox("Тема", topics, key="sel_topic")
        with c2:
            num_questions = st.number_input("Кол-во вопросов", min_value=1, max_value=50, value=10, key="sel_num")

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
                st.session_state.is_free_test = True
                st.rerun()
    else:
        if not st.session_state.get("test_questions"):
            st.info("👋 У вас нет активных заданий. Пожалуйста, ожидайте назначения теста от методиста.")


# ========== ЭКРАН 2: ПРОХОЖДЕНИЕ ТЕСТА ==========
elif not st.session_state.get("test_finished"):
    qs = st.session_state.test_questions
    idx = st.session_state.current_q
    q = qs[idx]

    c_prog, c_timer = st.columns([3, 1])
    with c_prog:
        st.progress(idx / len(qs), text=f"Вопрос {idx + 1} из {len(qs)}")
    
    with c_timer:
        if st.session_state.get("test_end_time"):
            @st.fragment(run_every=1.0)
            def show_timer():
                remaining = int(st.session_state.test_end_time - time.time())
                if remaining > 0:
                    mins, secs = divmod(remaining, 60)
                    st.warning(f"⏳ **{mins:02d}:{secs:02d}**")
                else:
                    st.error("⏰ **Время вышло!**")
                    st.session_state.test_finished = True
                    st.rerun()
            show_timer()
        else:
            st.write("⏳ Без лимита")

    # --- ОТОБРАЖЕНИЕ ТЕКСТА И ГЛАВНОЙ КАРТИНКИ ---
    st.subheader(q["question"])
    if q.get("image_path") and os.path.exists(q["image_path"]):
        st.image(q["image_path"], width=300)

    options = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
    option_images = q.get("option_images") or []
    
    # Распаковка правильных ответов
    raw_correct = q["correct_answer"]
    if isinstance(raw_correct, str):
        try:
            correct_indices = json.loads(raw_correct)
        except:
            correct_indices = [0]
    else:
        correct_indices = [raw_correct] if isinstance(raw_correct, int) else raw_correct
        
    correct_indices = _flatten(correct_indices)

    is_multi = len(correct_indices) > 1
    selected_indices = []

    # --- ЛОГИКА ВЫБОРА ---
    if is_multi:
        st.info("ℹ️ **Выберите все правильные варианты**")
        for i, opt in enumerate(options):
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.checkbox(f"{chr(65 + i)}", key=f"cb_{idx}_{i}"):
                    selected_indices.append(i)
            with col2:
                if i < len(option_images) and option_images[i] and os.path.exists(option_images[i]):
                    st.image(option_images[i], width=100)
                else:
                    st.write(opt)
    else:
        # Для одиночного выбора (радиокнопки)
        labels = [f"{chr(65 + i)}. {o}" for i, o in enumerate(options)]
        choice = st.radio("Вариант ответа", labels, key=f"radio_{idx}")
        selected_idx = labels.index(choice)
        selected_indices = [selected_idx]

        # Выводим картинку выбранного варианта прямо под кнопками
        if selected_idx < len(option_images) and option_images[selected_idx] and os.path.exists(option_images[selected_idx]):
            st.image(option_images[selected_idx], width=200)
    # --- КНОПКИ НАВИГАЦИИ ---
    c1, c2 = st.columns([1, 1])
    with c1:
        if idx > 0 and st.button("⬅️ Назад", use_container_width=True):
            st.session_state.current_q -= 1
            st.rerun()
    with c2:
        btn_label = "Завершить ✅" if idx == len(qs) - 1 else "Далее ➡️"
        if st.button(btn_label, type="primary", use_container_width=True):
            # Сохраняем ответ
            st.session_state.answers[idx] = selected_indices

            if idx == len(qs) - 1:
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
    
    score = 0
    for i, q in enumerate(qs):
        user_ans = ans.get(i, [])
        if not isinstance(user_ans, list): user_ans = [user_ans]
        
        raw_correct = q["correct_answer"]
        if isinstance(raw_correct, str):
            try: correct_ans = json.loads(raw_correct)
            except: correct_ans = [0]
        else:
            correct_ans = [raw_correct] if isinstance(raw_correct, int) else raw_correct
            
        user_ans_flat = _flatten(user_ans)
        correct_ans_flat = _flatten(correct_ans)
            
        if set(user_ans_flat) == set(correct_ans_flat):
            score += 1
            
    pct = score / len(qs) * 100

    if not st.session_state.get("balloons_shown"):
        st.balloons()
        st.session_state.balloons_shown = True

    st.success(f"### Результат: {score} из {len(qs)} ({pct:.1f}%)")

    if not st.session_state.get("result_saved"):
        assignment_id = st.session_state.get("assignment_id")
        group_id = None
        if assignment_id:
            assignment = db.get_assignment(assignment_id)
            group_id = assignment["group_id"] if assignment else None
        elif "impersonate_group_id" in st.session_state:
            group_id = st.session_state["impersonate_group_id"]
        else:
            user_groups = db.get_user_groups(st.session_state.user_id)
            group_id = user_groups[0]["id"] if len(user_groups) == 1 else None

        is_training = False
        if assignment_id:
            assignment = db.get_assignment(assignment_id)
            if assignment and assignment.get("is_training"):
                is_training = True

        if is_training:
            st.toast("🎓 Это была тренировка. Результат не сохранен.", icon="ℹ️")
        else:
            answers_detail = []
            for i, q in enumerate(qs):
                opts = json.loads(q["options"])
                user_ans = ans.get(i, [])
                if not isinstance(user_ans, list): user_ans = [user_ans]
                
                raw_c = q["correct_answer"]
                if isinstance(raw_c, str):
                    try: c_ans = json.loads(raw_c)
                    except: c_ans = [0]
                else: c_ans = [raw_c]

                user_ans_flat = _flatten(user_ans)
                c_ans_flat = _flatten(c_ans)

                answers_detail.append({
                    "question_id": q["id"], "question_text": q["question"],
                    "options": opts, "user_answer_idx": user_ans_flat, 
                    "correct_answer_idx": c_ans_flat, 
                    "is_correct": set(user_ans_flat) == set(c_ans_flat)
                })

            db.save_result(
                user_id=st.session_state.user_id, user_name=st.session_state.user,
                topic=st.session_state.get("test_topic", "Все"), answers=answers_detail,
                score=score, total=len(qs), time_spent=int(time.time() - st.session_state.test_start),
                group_id=group_id, assignment_id=assignment_id,
            )
        st.session_state.result_saved = True

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("❌ Закрыть", type="primary", use_container_width=True):
            _reset_test_state()
            st.rerun()
    if st.session_state.get("is_free_test"):
        with c2:
            if st.button("🔄 Пройти ещё раз", use_container_width=True):
                _reset_test_state()
                st.rerun()
    with c3:
        if st.button("📊 Мои результаты", use_container_width=True):
            st.switch_page("pages/2_📊_Результаты.py")

    if st.session_state.get("role") in ("admin", "methodist"):
        with st.expander("📋 Детальный просмотр ответов"):
            for i, q in enumerate(qs):
                options = json.loads(q["options"])
                user_ans = ans.get(i, [])
                if not isinstance(user_ans, list): user_ans = [user_ans]
                
                raw_c = q["correct_answer"]
                if isinstance(raw_c, str):
                    try: c_ans = json.loads(raw_c)
                    except: c_ans = [0]
                else: c_ans = [raw_c]

                user_ans_flat = _flatten(user_ans)
                c_ans_flat = _flatten(c_ans)

                if q.get("image_path") and os.path.exists(q["image_path"]):
                    st.image(q["image_path"], width=300)
                    
                st.markdown(f"**Вопрос {i + 1}: {q['question']}**")
                
                for opt_i, opt_text in enumerate(options):
                    is_user = opt_i in user_ans_flat
                    is_correct = opt_i in c_ans_flat
                    
                    if is_correct and is_user:
                        st.success(f"✅ **{chr(65 + opt_i)}. {opt_text}** *(Выбрано верно)*")
                    elif is_correct:
                        st.info(f"ℹ️ **{chr(65 + opt_i)}. {opt_text}** *(Правильный ответ)*")
                    elif is_user:
                        st.error(f"❌ **{chr(65 + opt_i)}. {opt_text}** *(Выбрано неверно)*")
                    else:
                        st.write(f"▫️ {chr(65 + opt_i)}. {opt_text}")
                
                st.divider()