"""📌 Управление заданиями для групп."""
import streamlit as st
import pandas as pd
import datetime as _dt
from datetime import datetime, time as _time

from utils.session import restore_session
from utils.navigation import setup_page
from database import Database
from utils.auth import require_methodist

st.set_page_config(page_title="Задания", page_icon="📌", layout="wide")
restore_session()
setup_page()
require_methodist()

@st.cache_resource
def get_db():
    return Database()

db = get_db()
USER_ID = st.session_state.user_id

STATUS_LABELS = {
    "open": "🟢 Открыто",
    "closed": "🔒 Закрыто",
    "archived": "🗄️ В архиве",
}

st.title("📌 Управление заданиями")
st.caption("Создание и мониторинг тестов для групп")

# ==================================================================
# ДИАЛОГ 1: ДЕТАЛИ ЗАДАНИЯ (ВСПЛЫВАЮЩЕЕ ОКНО)
# ==================================================================
@st.dialog("Детали задания", width="large")
def show_assignment_details(aid):
    assignment = db.get_assignment(aid)
    stats_a = db.get_assignment_statistics(aid)
    
    if not assignment:
        st.error("Задание не найдено")
        return

    st.subheader(f"{assignment['title'] or 'Без названия'}")
    st.caption(f"Группа: **{assignment['group_name']}** | Тема: {assignment['topic'] or 'Все'}")
    
    if assignment.get("is_training"):
        st.info("🎓 **Это тренировочное задание.** Результаты не сохраняются в статистику.")

    # --- УПРАВЛЕНИЕ СТАТУСОМ ---
    c_stat1, c_stat2 = st.columns(2)
    with c_stat1:
        if assignment["status"] == "open":
            if st.button("🔒 Закрыть задание", type="primary", use_container_width=True):
                db.update_assignment(aid, status="closed")
                db.log_action(USER_ID, "assignment_close", f"Задание #{aid} закрыто")
                st.rerun()
        elif assignment["status"] == "closed":
            if st.button("♻️ Открыть снова", type="primary", use_container_width=True):
                db.update_assignment(aid, status="open")
                db.log_action(USER_ID, "assignment_reopen", f"Задание #{aid} открыто повторно")
                st.rerun()
                
    with c_stat2:
        if assignment["status"] != "archived":
            if st.button("🗄️ В архив", use_container_width=True):
                db.update_assignment(aid, status="archived")
                db.log_action(USER_ID, "assignment_archive", f"Задание #{aid} в архиве")
                st.rerun()

    st.divider()
    
    info = stats_a.get("info") or {}
    total = info.get("total_students") or 0
    students = stats_a.get("students") or []
    passed = sum(1 for s in students if (s.get("best_score") or 0) >= assignment["pass_score"])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Проходной", f"{assignment['pass_score']}%")
    c2.metric("Сдали", f"{passed} / {total}")
    if total > 0:
        avg = sum((s.get("best_score") or 0) for s in students) / total
        c3.metric("Средний балл", f"{avg:.1f}%")

    if students:
        df_students = pd.DataFrame([
            {
                "ФИО": s["full_name"] or s["username"], 
                "Попыток": s["attempts"] or 0, 
                "Лучший %": round(s["best_score"] or 0, 1),
                "Последняя попытка": s["last_attempt"].strftime("%d.%m %H:%M") if s.get("last_attempt") else "—",
                "Статус": "✅ Сдал" if (s.get("best_score") or 0) >= assignment["pass_score"] else "⏳ В процессе",
            }
            for s in students
        ])
        st.dataframe(df_students, use_container_width=True, hide_index=True)
    else:
        st.info("В группе пока нет участников.")


# ==================================================================
# ДИАЛОГ 2: РЕДАКТИРОВАНИЕ ЗАДАНИЯ
# ==================================================================
@st.dialog("Редактирование задания", width="large")
def edit_assignment_dialog(aid):
    assignment = db.get_assignment(aid)
    if not assignment:
        st.error("Задание не найдено")
        return

    st.caption(f"Группа: **{assignment['group_name']}** (нельзя изменить)")
    
    with st.form(f"edit_assign_form_{aid}"):
        c1, c2 = st.columns(2)
        with c1:
            topics = ["Все темы"] + db.get_all_topics(include_archived=True)
            current_topic = assignment["topic"] or "Все темы"
            t_index = topics.index(current_topic) if current_topic in topics else 0
            
            e_topic = st.selectbox("Тема", topics, index=t_index)
            e_title = st.text_input("Название задания", value=assignment["title"] or "")
            e_desc = st.text_area("Описание", value=assignment["description"] or "", height=100)
        with c2:
            e_num = st.number_input("Количество вопросов", 1, 50, value=assignment["num_questions"])
            e_pass = st.slider("Проходной балл, %", 0, 100, value=assignment["pass_score"], step=5)
            e_time = st.number_input("Лимит времени, мин (0 = без)", 0, 300, value=assignment["time_limit_min"] or 0)
            
            # --- РЕДАКТИРОВАНИЕ ФЛАГА ТРЕНИРОВКИ ---
            e_is_training = st.checkbox("Тренировочное (без сохранения результата)", value=bool(assignment.get("is_training")))
            
            default_due_date = assignment["due_date"].date() if assignment.get("due_date") else None
            e_due_date = st.date_input("Дедлайн (дата)", value=default_due_date)
            
            if e_due_date:
                default_due_time = assignment["due_date"].time() if assignment.get("due_date") else _time(23, 59)
                e_due_time = st.time_input("Дедлайн (время)", value=default_due_time)
            else:
                e_due_time = _time(23, 59)

        if st.form_submit_button("💾 Сохранить изменения", type="primary", use_container_width=True):
            due = None
            if e_due_date:
                due = datetime.combine(e_due_date, e_due_time)

            topic_value = None if e_topic == "Все темы" else e_topic
            time_limit = e_time if e_time > 0 else None

            db.update_assignment(
                aid,
                topic=topic_value,
                num_questions=e_num,
                time_limit_min=time_limit,
                pass_score=e_pass,
                title=e_title.strip() or None,
                description=e_desc.strip() or None,
                due_date=due,
                is_training=e_is_training
            )
            db.log_action(USER_ID, "assignment_update", f"Задание #{aid} обновлено")
            st.success("✅ Сохранено!")
            st.rerun()


# ==================================================================
# АВТООТКРЫТИЕ ДИАЛОГА ПРИ ПЕРЕХОДЕ С ДАШБОРДА
# ==================================================================
target_aid = st.session_state.pop("target_assignment_id", None)
if target_aid:
    show_assignment_details(target_aid)


# ==================================================================
# 1. СОЗДАНИЕ ЗАДАНИЯ
# ==================================================================
with st.expander("➕ Создать новое задание", expanded=False):
    groups = db.get_all_groups(only_active=True)
    if not groups:
        st.warning("Сначала создайте хотя бы одну группу в разделе 👥 Группы")
    else:
        group_map = {f"{g['name']} ({g['member_count']} чел.)": g["id"] for g in groups}
        topics = ["Все темы"] + db.get_all_topics(include_archived=False)

        with st.form("create_assignment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                a_group_label = st.selectbox("Группа *", list(group_map.keys()))
                a_topic = st.selectbox("Тема", topics)
                a_title = st.text_input("Название задания", placeholder="Аттестация по Python, декабрь 2026")
                a_desc = st.text_area("Описание", height=80)
            with c2:
                a_num = st.number_input("Количество вопросов", 1, 50, 10)
                a_attempts = st.number_input("Макс. попыток", 1, 10, 1)
                a_pass = st.slider("Проходной балл, %", 0, 100, 60, 5)
                a_time = st.number_input("Ограничение времени, мин (0 = без)", 0, 300, 0)
                
                # --- ФЛАГ ТРЕНИРОВКИ ПРИ СОЗДАНИИ ---
                a_is_training = st.checkbox("Тренировочное (без сохранения результата)", value=False)

            c_due1, c_due2 = st.columns(2)
            with c_due1:
                a_due_date = st.date_input("Дедлайн (дата)", value=None)
            with c_due2:
                a_due_time = st.time_input("Дедлайн (время)", value=None)

            if st.form_submit_button("✅ Создать", type="primary"):
                due = None
                if a_due_date:
                    t = a_due_time if a_due_time else _time(23, 59)
                    due = datetime.combine(a_due_date, t)

                topic_value = None if a_topic == "Все темы" else a_topic
                time_limit = a_time if a_time > 0 else None

                aid = db.create_assignment(
                    group_id=group_map[a_group_label], topic=topic_value,
                    num_questions=a_num, max_attempts=a_attempts,
                    time_limit_min=time_limit, pass_score=a_pass,
                    title=a_title.strip() or None, description=a_desc.strip() or None,
                    due_date=due, created_by=st.session_state.user,
                    is_training=a_is_training
                )
                db.log_action(USER_ID, "assignment_create", f"Задание #{aid} для группы {a_group_label}")
                st.success(f"✅ Задание создано (ID: {aid})")
                st.rerun()

st.divider()

# ==================================================================
# 2. СПИСОК ЗАДАНИЙ (КАРТОЧКИ) С ПАГИНАЦИЕЙ
# ==================================================================
c_filter, c_page = st.columns([3, 2])

with c_filter:
    status_filter_map = {
        "Все": None,
        "🟢 Открытые": "open",
        "🔒 Закрытые": "closed",
        "🗄️ В архиве": "archived",
    }
    f_status_label = st.selectbox("Фильтр по статусу", list(status_filter_map.keys()), key="a_filter")
    f_status = status_filter_map[f_status_label]

# Получаем все задания по фильтру
all_assignments = db.get_all_assignments(status=f_status)

if not all_assignments:
    st.info("📌 Заданий пока нет. Создайте первое в блоке выше.")
else:
    # --- ПАГИНАЦИЯ ---
    PAGE_SIZE = 10
    total_items = len(all_assignments)
    total_pages = (total_items - 1) // PAGE_SIZE + 1

    with c_page:
        # Выбор страницы (только если страниц больше одной)
        if total_pages > 1:
            page_num = st.number_input(
                f"Страница (всего: {total_pages})", 
                min_value=1, 
                max_value=total_pages, 
                value=1, 
                step=1, 
                key="assign_page"
            )
        else:
            page_num = 1

    # Нарезаем список
    start_idx = (page_num - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_assignments = all_assignments[start_idx:end_idx]

    st.caption(f"Показано {start_idx + 1}–{min(end_idx, total_items)} из {total_items} заданий")

    # --- ОТРИСОВКА КАРТОЧЕК ---
    for a in page_assignments:
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 3, 2])
            
            with c1:
                st.markdown(f"### {a['title'] or 'Без названия'}")
                st.caption(f"**Группа:** {a['group_name']} | **Тема:** {a['topic'] or 'Все'} | **Вопросов:** {a['num_questions']}")
                
                # Метка тренировки
                if a.get("is_training"):
                    st.markdown("🎓 **Тренировочное (без сохранения)**")
                
                if a.get("due_date"):
                    now = datetime.now()
                    due = a["due_date"]
                    delta = due - now
                    due_str = due.strftime('%d.%m.%Y %H:%M')
                    
                    # Проверяем, не прошел ли дедлайн и сколько осталось
                    if delta.total_seconds() < 0:
                        st.markdown(
                            f"📅 **Дедлайн:** <span style='color: #E74C3C; font-weight: bold;'>{due_str} (просрочено!)</span>", 
                            unsafe_allow_html=True
                        )
                    elif delta.total_seconds() < 172800: # 172800 секунд = 48 часов (2 дня)
                        st.markdown(
                            f"📅 **Дедлайн:** <span style='color: #F39C12; font-weight: bold;'>{due_str} (осталось < 2 дней!)</span>", 
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(f"📅 **Дедлайн:** `{due_str}`")
                else:
                    st.markdown("📅 **Дедлайн:** _без ограничения_")
                    
            with c2:
                total_students = a.get("total_students") or 1
                completed = a.get("completed_count") or 0
                progress_pct = int((completed / total_students) * 100)
                
                st.write(f"**Прогресс сдачи:** {completed} из {total_students}")
                st.progress(progress_pct / 100, text=f"{progress_pct}%")
                
                c_info1, c_info2 = st.columns(2)
                c_info1.metric("Проходной", f"{a['pass_score']}%")
                c_info2.metric("Попыток", a['max_attempts'])

            with c3:
                status_text = STATUS_LABELS.get(a["status"], a["status"])
                if a["status"] == "open":
                    st.success(status_text)
                elif a["status"] == "closed":
                    st.warning(status_text)
                else:
                    st.info(status_text)
                
                if st.button("👁️ Детали", key=f"view_assign_{a['id']}", use_container_width=True):
                    show_assignment_details(a["id"])
                
                if st.button("✏️ Редактировать", key=f"edit_assign_{a['id']}", use_container_width=True):
                    edit_assignment_dialog(a["id"])