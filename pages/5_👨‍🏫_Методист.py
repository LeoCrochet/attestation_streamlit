"""👨‍🏫 Кабинет методиста — редактор вопросов и тем."""
import json as _json

import pandas as pd
import plotly.express as px
import streamlit as st

from database import Database
from utils.auth import require_methodist
from utils.question_io import (
    parse_csv, parse_json,
    questions_to_csv, questions_to_json,
    build_csv_template, build_json_template,
    CORRECT_LETTERS,
)

st.set_page_config(page_title="Кабинет методиста", page_icon="👨‍🏫", layout="wide")
require_methodist()


@st.cache_resource
def get_db():
    return Database()


db = get_db()

st.title("👨‍🏫 Кабинет методиста")
st.caption("Редактор вопросов, тем и содержания")


tab_q, tab_add, tab_import, tab_export, tab_stats, tab_assign = st.tabs([
    "📋 Редактор вопросов",
    "➕ Новый вопрос",
    "📥 Импорт",
    "📤 Экспорт",
    "📊 Статистика банка",
    "📌 Задания",
])



# ==================================================================
# ВКЛАДКА 1: РЕДАКТОР ВОПРОСОВ
# ==================================================================
with tab_q:
    st.subheader("📋 Банк вопросов")

    with st.expander("🔍 Фильтры", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        with c1:
            topics = ["Все"] + db.get_all_topics(include_archived=True)
            f_topic = st.selectbox("Тема", topics, key="m_topic")
        with c2:
            f_search = st.text_input("Поиск по тексту/тегам", key="m_search")
        with c3:
            f_diff = st.selectbox("Сложность", ["Все", 1, 2, 3, 4, 5], key="m_diff")
        with c4:
            f_active = st.selectbox(
                "Статус", ["Только активные", "Только архив", "Все"], key="m_active",
            )

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        page_size = st.selectbox("На странице", [10, 25, 50, 100], index=1,
                                 key="m_page_size")
    with c2:
        page_num = st.number_input("Страница", min_value=1, value=1, step=1,
                                   key="m_page_num")
    offset = (page_num - 1) * page_size

    is_active_param = {
        "Только активные": True, "Только архив": False, "Все": None,
    }[f_active]

    rows, total = db.get_questions_paginated(
        topic=f_topic,
        search=f_search or None,
        difficulty=f_diff if f_diff != "Все" else None,
        is_active=is_active_param,
        limit=page_size,
        offset=offset,
    )

    st.caption(
        f"Найдено: **{total}** вопросов | Страница {page_num} из "
        f"{(total + page_size - 1) // page_size or 1}"
    )

    if not rows:
        st.info("Ничего не найдено")
    else:
        display = []
        for r in rows:
            display.append({
                "✓": False,
                "ID": r["id"],
                "Тема": r["topic"],
                "Вопрос": r["question"][:80] + ("…" if len(r["question"]) > 80 else ""),
                "Правильный": CORRECT_LETTERS[r["correct_answer"]] if r["correct_answer"] < 4 else "?",
                "Сложность": "⭐" * r["difficulty"],
                "Теги": r["tags"] or "",
                "Активен": "✅" if r["is_active"] else "🗄️",
            })

        df = pd.DataFrame(display)
        edited = st.data_editor(
            df, hide_index=True, use_container_width=True,
            column_config={
                "✓": st.column_config.CheckboxColumn("✓", width="small"),
                "ID": st.column_config.NumberColumn("ID", width="small", disabled=True),
                "Сложность": st.column_config.TextColumn(width="small"),
                "Активен": st.column_config.TextColumn(width="small"),
            },
            disabled=["ID", "Тема", "Вопрос", "Правильный", "Сложность", "Теги", "Активен"],
            key="m_table",
        )

        selected_ids = edited.loc[edited["✓"], "ID"].tolist()

        if selected_ids:
            st.info(f"Выбрано: **{len(selected_ids)}** вопросов")
            mc1, mc2, mc3, mc4 = st.columns(4)

            with mc1:
                new_topic = st.text_input("Новая тема", key="m_bulk_topic")
                if st.button("📁 Переместить", use_container_width=True, key="m_move"):
                    if new_topic.strip():
                        n = db.bulk_update_topic(
                            selected_ids, new_topic.strip(),
                            updated_by=st.session_state.user,
                        )
                        st.success(f"Перемещено: {n}")
                        st.rerun()

            with mc2:
                new_diff = st.selectbox("Сложность", [1, 2, 3, 4, 5], key="m_bulk_diff")
                if st.button("⭐ Изменить", use_container_width=True, key="m_diff_btn"):
                    n = db.bulk_update_difficulty(
                        selected_ids, new_diff,
                        updated_by=st.session_state.user,
                    )
                    st.success(f"Обновлено: {n}")
                    st.rerun()

            with mc3:
                if st.button("🗄️ В архив", use_container_width=True, key="m_arch"):
                    n = db.bulk_delete_questions(
                        selected_ids, deleted_by=st.session_state.user,
                    )
                    st.success(f"В архив: {n}")
                    st.rerun()

            with mc4:
                ck = "m_confirm_hard_del"
                if st.session_state.get(ck) == tuple(selected_ids):
                    if st.button("⚠️ Удалить навсегда", type="primary",
                                 use_container_width=True, key="m_hd_ok"):
                        for qid in selected_ids:
                            db.hard_delete_question(qid, deleted_by=st.session_state.user)
                        st.session_state[ck] = None
                        st.success(f"Удалено: {len(selected_ids)}")
                        st.rerun()
                else:
                    if st.button("⚠️ Удалить навсегда", use_container_width=True, key="m_hd"):
                        st.session_state[ck] = tuple(selected_ids)
                        st.warning("Нажмите ещё раз для подтверждения")
                        st.rerun()

        # Редактор одного вопроса
        st.divider()
        st.subheader("✏️ Редактировать вопрос")
        c1, c2 = st.columns([1, 3])
        with c1:
            qid = st.number_input("ID вопроса", min_value=1, step=1, key="m_edit_qid")
        with c2:
            if st.button("Загрузить", key="m_load_edit"):
                st.session_state["m_edit_q"] = db.get_question_by_id(qid)

        if st.session_state.get("m_edit_q"):
            q = st.session_state["m_edit_q"]
            with st.form(f"m_edit_form_{q['id']}"):
                e_topic = st.text_input("Тема", value=q["topic"])
                e_question = st.text_area("Вопрос", value=q["question"], height=100)
                opts = _json.loads(q["options"])
                cols = st.columns(2)
                e_opts = []
                for i, o in enumerate(opts):
                    with cols[i % 2]:
                        e_opts.append(st.text_input(
                            f"Вариант {CORRECT_LETTERS[i]}", value=o, key=f"m_eopt_{i}",
                        ))
                e_correct = st.selectbox(
                    "Правильный ответ",
                    options=range(len(e_opts)),
                    format_func=lambda i: f"{CORRECT_LETTERS[i]}. {e_opts[i][:40]}",
                    index=q["correct_answer"],
                )
                c1, c2 = st.columns(2)
                with c1:
                    e_diff = st.slider("Сложность", 1, 5, q["difficulty"])
                    e_tags = st.text_input("Теги", value=q["tags"] or "")
                with c2:
                    e_active = st.checkbox("Активен", value=bool(q["is_active"]))
                e_expl = st.text_area("Пояснение", value=q["explanation"] or "")

                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.form_submit_button("💾 Сохранить", type="primary",
                                             use_container_width=True):
                        db.update_question(
                            q["id"],
                            topic=e_topic, question=e_question, options=e_opts,
                            correct_answer=e_correct, difficulty=e_diff,
                            tags=e_tags or None, explanation=e_expl or None,
                            is_active=e_active,
                            updated_by=st.session_state.user,
                        )
                        st.success("Сохранено")
                        del st.session_state["m_edit_q"]
                        st.rerun()
                with c2:
                    if st.form_submit_button("❌ Отмена", use_container_width=True):
                        del st.session_state["m_edit_q"]
                        st.rerun()


# ==================================================================
# ВКЛАДКА 2: НОВЫЙ ВОПРОС
# ==================================================================
with tab_add:
    st.subheader("➕ Новый вопрос")
    with st.form("m_add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            a_topic = st.text_input("Тема *", key="m_a_topic")
            a_question = st.text_area("Вопрос *", height=120, key="m_a_q")
            a_expl = st.text_area("Пояснение к ответу", height=80, key="m_a_expl")
        with c2:
            a_opt_a = st.text_input("Вариант A *", key="m_a_a")
            a_opt_b = st.text_input("Вариант B *", key="m_a_b")
            a_opt_c = st.text_input("Вариант C *", key="m_a_c")
            a_opt_d = st.text_input("Вариант D *", key="m_a_d")
            a_correct = st.selectbox("Правильный ответ *", ["A", "B", "C", "D"], key="m_a_corr")
            a_diff = st.slider("Сложность", 1, 5, 1, key="m_a_diff")
            a_tags = st.text_input("Теги (через запятую)", key="m_a_tags")

        submitted = st.form_submit_button("💾 Добавить", type="primary")

        if submitted:
            opts = [a_opt_a, a_opt_b, a_opt_c, a_opt_d]
            opts = [o for o in opts if o.strip()]

            if not a_topic.strip() or not a_question.strip() or len(opts) < 2:
                st.error("Заполните тему, вопрос и минимум 2 варианта")
            else:
                correct_index = CORRECT_LETTERS.index(a_correct)
                if correct_index >= len(opts):
                    st.error("Правильный ответ указывает на пустой вариант")
                else:
                    new_id = db.add_question(
                        topic=a_topic.strip(), question=a_question.strip(),
                        options=opts, correct_answer=correct_index,
                        difficulty=a_diff, created_by=st.session_state.user,
                        tags=a_tags.strip() or None,
                        explanation=a_expl.strip() or None,
                    )
                    db.log_action(st.session_state.user_id, "question_add",
                                  f"Добавлен вопрос ID: {new_id}")
                    st.success(f"✅ Вопрос добавлен (ID: {new_id})")


# ==================================================================
# ВКЛАДКА 3: ИМПОРТ
# ==================================================================
with tab_import:
    st.subheader("📥 Импорт вопросов")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📄 Шаблон CSV",
            data=build_csv_template().encode("utf-8-sig"),
            file_name="questions_template.csv", mime="text/csv",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "📄 Шаблон JSON",
            data=build_json_template().encode("utf-8"),
            file_name="questions_template.json", mime="application/json",
            use_container_width=True,
        )

    st.divider()
    uploaded = st.file_uploader("Выберите файл", type=["csv", "json"], key="m_up")

    if uploaded is not None:
        file_bytes = uploaded.read()
        fname = uploaded.name.lower()

        if fname.endswith(".csv"):
            questions, errors = parse_csv(file_bytes)
        elif fname.endswith(".json"):
            questions, errors = parse_json(file_bytes)
        else:
            questions, errors = [], ["Поддерживаются только .csv и .json"]

        if errors:
            st.error(f"Найдено ошибок: **{len(errors)}**")
            with st.expander("Показать ошибки", expanded=True):
                for e in errors[:50]:
                    st.write("• " + e)

        if questions:
            st.success(f"✅ Валидных вопросов: **{len(questions)}**")

            with st.expander("Предпросмотр (первые 5)"):
                for q in questions[:5]:
                    st.write(f"**{q['topic']}**: {q['question']}")
                    for i, o in enumerate(q["options"]):
                        mark = "✅" if i == q["correct_answer"] else "▫️"
                        st.write(f"  {mark} {CORRECT_LETTERS[i]}. {o}")
                    st.divider()

            if st.button(f"📥 Импортировать {len(questions)}", type="primary",
                         use_container_width=True, key="m_import_btn"):
                added, errs = db.bulk_add_questions(
                    questions, created_by=st.session_state.user,
                )
                db.log_action(st.session_state.user_id, "questions_import",
                              f"Импортировано: {added} из {len(questions)}")
                st.success(f"✅ Импортировано: **{added}**")
                if errs:
                    st.warning(f"Ошибок: {len(errs)}")
                    for e in errs[:20]:
                        st.write("• " + e)


# ==================================================================
# ВКЛАДКА 4: ЭКСПОРТ
# ==================================================================
with tab_export:
    st.subheader("📤 Экспорт вопросов")

    e1, e2, e3 = st.columns([2, 1, 1])
    with e1:
        export_topic = st.selectbox(
            "Тема", ["Все темы"] + db.get_all_topics(include_archived=True),
            key="m_exp_topic",
        )
    with e2:
        export_active = st.selectbox(
            "Статус", ["Только активные", "Все", "Только архив"], key="m_exp_active",
        )
    with e3:
        export_format = st.selectbox("Формат", ["CSV", "JSON"], key="m_exp_fmt")

    is_active_map = {"Только активные": True, "Все": None, "Только архив": False}

    exp_rows, _ = db.get_questions_paginated(
        topic=export_topic,
        is_active=is_active_map[export_active],
        limit=100000, offset=0,
    )

    if exp_rows:
        st.caption(f"К экспорту: **{len(exp_rows)}** вопросов")
        import datetime as _dt
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

        if export_format == "CSV":
            data = questions_to_csv(exp_rows).encode("utf-8-sig")
            fname, mime = f"questions_{ts}.csv", "text/csv"
        else:
            data = questions_to_json(exp_rows).encode("utf-8")
            fname, mime = f"questions_{ts}.json", "application/json"

        st.download_button(
            f"📥 Скачать {export_format}", data=data, file_name=fname,
            mime=mime, use_container_width=True, type="primary",
        )
    else:
        st.info("Нет вопросов для экспорта")


# ==================================================================
# ВКЛАДКА 5: СТАТИСТИКА БАНКА
# ==================================================================
with tab_stats:
    st.subheader("📊 Статистика банка вопросов")

    stats = db.get_questions_stats()

    if stats and stats.get("overall"):
        o = stats["overall"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Всего", o["total"] or 0)
        c2.metric("Активных", o["active"] or 0)
        c3.metric("В архиве", o["archived"] or 0)
        c4.metric("Тем", o["topics"] or 0)
        c5.metric("Ср. сложность", f"{(o['avg_difficulty'] or 0):.1f}")

    if stats and stats.get("by_topic"):
        st.divider()
        st.write("### 📚 По темам")
        df_topics = pd.DataFrame(stats["by_topic"])
        fig = px.bar(
            df_topics, x="topic", y="cnt", text="cnt",
            labels={"topic": "Тема", "cnt": "Кол-во вопросов"},
            color="cnt", color_continuous_scale="Blues",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            df_topics.rename(columns={
                "topic": "Тема", "cnt": "Вопросов",
                "avg_diff": "Ср. сложность", "archived": "В архиве",
            }),
            use_container_width=True, hide_index=True,
        )

    if stats and stats.get("by_difficulty"):
        st.divider()
        st.write("### ⭐ По сложности")
        df_diff = pd.DataFrame(stats["by_difficulty"])
        fig = px.pie(
            df_diff, names="difficulty", values="cnt",
            labels={"difficulty": "Сложность", "cnt": "Кол-во"},
            hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)


# ==================================================================
# ВКЛАДКА: ЗАДАНИЯ
# ==================================================================
with tab_assign:
    st.subheader("📌 Задания для групп")

    # ---------- Создание ----------
    with st.expander("➕ Создать задание", expanded=False):
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
                    a_title = st.text_input("Название задания",
                                            placeholder="Аттестация по Python, декабрь 2026")
                    a_desc = st.text_area("Описание", height=80)
                with c2:
                    a_num = st.number_input("Количество вопросов", 1, 50, 10)
                    a_attempts = st.number_input("Макс. попыток", 1, 10, 1)
                    a_pass = st.slider("Проходной балл, %", 0, 100, 60, 5)
                    a_time = st.number_input("Ограничение времени, мин (0 = без)", 0, 300, 0)

                c_due1, c_due2 = st.columns(2)
                with c_due1:
                    a_due_date = st.date_input("Дедлайн (дата)", value=None)
                with c_due2:
                    a_due_time = st.time_input("Дедлайн (время)", value=None)

                if st.form_submit_button("✅ Создать", type="primary"):
                    from datetime import datetime, time as _time
                    due = None
                    if a_due_date:
                        t = a_due_time if a_due_time else _time(23, 59)
                        due = datetime.combine(a_due_date, t)

                    topic_value = None if a_topic == "Все темы" else a_topic
                    time_limit = a_time if a_time > 0 else None

                    aid = db.create_assignment(
                        group_id=group_map[a_group_label],
                        topic=topic_value,
                        num_questions=a_num,
                        max_attempts=a_attempts,
                        time_limit_min=time_limit,
                        pass_score=a_pass,
                        title=a_title.strip() or None,
                        description=a_desc.strip() or None,
                        due_date=due,
                        created_by=st.session_state.user,
                    )
                    db.log_action(
                        st.session_state.user_id, "assignment_create",
                        f"Задание #{aid} для группы {a_group_label}",
                    )
                    st.success(f"✅ Задание создано (ID: {aid})")
                    st.rerun()

    # ---------- Список заданий ----------
    st.divider()
    st.subheader("📋 Все задания")

    f_status = st.selectbox(
        "Фильтр по статусу", ["Все", "open", "closed", "archived"], key="a_filter",
    )
    assignments = db.get_all_assignments(
        status=None if f_status == "Все" else f_status,
    )

    if not assignments:
        st.info("Заданий пока нет")
    else:
        df_a = pd.DataFrame([
            {
                "ID": a["id"],
                "Название": a["title"] or "—",
                "Группа": a["group_name"],
                "Тема": a["topic"] or "Все",
                "Вопросов": a["num_questions"],
                "Попыток": a["max_attempts"],
                "Проходной": f"{a['pass_score']}%",
                "Дедлайн": a["due_date"].strftime("%d.%m.%Y %H:%M") if a.get("due_date") else "—",
                "Сдали": f"{a['completed_count']} / {a['total_students']}",
                "Статус": a["status"],
            }
            for a in assignments
        ])
        st.dataframe(df_a, use_container_width=True, hide_index=True)

    # ---------- Детали задания ----------
    st.divider()
    st.subheader("🔍 Детали задания")

    if assignments:
        assign_map = {f"#{a['id']} — {a['title'] or a['group_name']}": a["id"]
                      for a in assignments}
        sel = st.selectbox("Выберите задание", list(assign_map.keys()), key="a_sel")
        aid = assign_map[sel]

        assignment = db.get_assignment(aid)
        stats = db.get_assignment_statistics(aid)

        if assignment:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Группа", assignment["group_name"])
            c2.metric("Тема", assignment["topic"] or "Все")
            c3.metric("Проходной", f"{assignment['pass_score']}%")
            info = stats.get("info") or {}
            total = info.get("total_students") or 0
            c4.metric("Студентов", total)

            students = stats.get("students") or []
            if students:
                passed = sum(1 for s in students
                             if (s.get("best_score") or 0) >= assignment["pass_score"])
                c1, c2, c3 = st.columns(3)
                c1.metric("Сдали", f"{passed} / {len(students)}")
                if len(students):
                    avg = sum((s.get("best_score") or 0) for s in students) / len(students)
                    c2.metric("Средний балл группы", f"{avg:.1f}%")

                df_students = pd.DataFrame([
                    {
                        "ФИО": s["full_name"] or s["username"],
                        "Логин": s["username"],
                        "Попыток": s["attempts"] or 0,
                        "Лучший %": round(s["best_score"] or 0, 1),
                        "Последняя попытка": (
                            s["last_attempt"].strftime("%d.%m.%Y %H:%M")
                            if s.get("last_attempt") else "—"
                        ),
                        "Статус": "✅ Сдал" if (s.get("best_score") or 0) >=
                                  assignment["pass_score"] else "⏳ В процессе",
                    }
                    for s in students
                ])
                st.dataframe(df_students, use_container_width=True, hide_index=True)

                # Экспорт
                from datetime import datetime as _dt
                ts = _dt.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    "📥 Скачать отчёт по заданию (CSV)",
                    data=df_students.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"assignment_{aid}_{ts}.csv",
                    mime="text/csv",
                )

            # Кнопки управления
            c1, c2 = st.columns(2)
            with c1:
                if assignment["status"] == "open":
                    if st.button("🔒 Закрыть задание", use_container_width=True):
                        db.close_assignment(aid)
                        db.log_action(st.session_state.user_id, "assignment_close",
                                      f"Задание #{aid} закрыто")
                        st.success("Задание закрыто")
                        st.rerun()
            with c2:
                if assignment["status"] != "archived":
                    if st.button("🗄️ Архивировать", use_container_width=True):
                        db.archive_assignment(aid)
                        db.log_action(st.session_state.user_id, "assignment_archive",
                                      f"Задание #{aid} в архиве")
                        st.success("Задание архивировано")
                        st.rerun()