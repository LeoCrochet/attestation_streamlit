"""👨‍🏫 Кабинет методиста — редактор вопросов, тем и статистика."""
import json as _json
import datetime as _dt

import pandas as pd
import plotly.express as px
import streamlit as st
import os

from utils.session import restore_session
from utils.navigation import setup_page
from database import Database
from utils.auth import require_methodist
from utils.question_io import (
    parse_csv, parse_json,
    questions_to_csv, questions_to_json,
    build_csv_template, build_json_template,
    CORRECT_LETTERS,
)

st.set_page_config(page_title="Кабинет методиста", page_icon="👨‍🏫", layout="wide")
restore_session()
setup_page()
require_methodist()

@st.cache_resource
def get_db():
    return Database()

db = get_db()

# --- ПРОВЕРКА ФЛАГА (если перешли из другой вкладки) ---
if "pending_edit_qid" in st.session_state:
    qid = st.session_state.pop("pending_edit_qid")
    st.session_state["m_edit_q"] = db.get_question_by_id(qid)

st.title("👨‍🏫 Кабинет методиста")

# ==================================================================
# СВОДНЫЕ МЕТРИКИ БАНКА ВОПРОСОВ
# ==================================================================
stats = db.get_questions_stats()
if stats and stats.get("overall"):
    o = stats["overall"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📚 Всего вопросов", o["total"] or 0)
    c2.metric("✅ Активных", o["active"] or 0)
    c3.metric("🗄️ В архиве", o["archived"] or 0)
    c4.metric("📁 Тем", o["topics"] or 0)

st.divider()

# Оставляем только 6 вкладок (без Заданий)
tab_q, tab_edit, tab_add, tab_import, tab_export, tab_stats = st.tabs([
    "📋 Банк вопросов",
    "✏️ Редактирование",
    "➕ Новый вопрос",
    "📥 Импорт",
    "📤 Экспорт",
    "📊 Статистика",
])

# ==================================================================
# ВКЛАДКА 1: БАНК ВОПРОСОВ
# ==================================================================
with tab_q:
    with st.expander("🔍 Фильтры", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
        with c1:
            topics = ["Все"] + db.get_all_topics(include_archived=True)
            f_topic = st.selectbox("Тема", topics, key="m_topic")
        with c2:
            f_search = st.text_input("Поиск по тексту/тегам", key="m_search")
        with c3:
            f_active = st.selectbox(
                "Статус", ["Только активные", "Только архив", "Все"], key="m_active",
            )
        with c4:
            all_tags = db.get_all_tags()
            f_tag = st.selectbox("Тег", ["Все теги"] + all_tags, key="m_tag_filter")

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        page_size = st.selectbox("На странице", [10, 25, 50, 100], index=1, key="m_page_size")
    with c2:
        page_num = st.number_input("Страница", min_value=1, value=1, step=1, key="m_page_num")
    offset = (page_num - 1) * page_size

    is_active_param = {"Только активные": True, "Только архив": False, "Все": None}[f_active]

    rows, total = db.get_questions_paginated(
        topic=f_topic,
        search=f_search or None,
        is_active=is_active_param,
        limit=page_size,
        offset=offset,
    )

    if f_tag != "Все теги":
        rows = [r for r in rows if r["tags"] and f_tag in r["tags"].split(",")]

    st.caption(
        f"Найдено: **{total}** вопросов | Страница {page_num} из "
        f"{(total + page_size - 1) // page_size or 1}"
    )

    if not rows:
        st.info("🔍 По вашим фильтрам ничего не найдено. Попробуйте изменить тему или сбросить поиск.")
    else:
        display = []
        for r in rows:
            display.append({
                "✓": False,
                "ID": r["id"],
                "Тема": r["topic"],
                "Вопрос": r["question"][:80] + ("…" if len(r["question"]) > 80 else ""),
                "Активен": "✅" if r["is_active"] else "🗄️",
            })

        df = pd.DataFrame(display)
        
        edited = st.data_editor(
            df, hide_index=True, use_container_width=True,
            column_config={
                "✓": st.column_config.CheckboxColumn("✓", width="small"),
                "ID": st.column_config.NumberColumn("ID", width="small", disabled=True),
                "Активен": st.column_config.TextColumn(width="small"),
            },
            disabled=["ID", "Тема", "Вопрос", "Активен"],
            key="m_table",
        )

        # Массовые действия
        selected_ids = edited.loc[edited["✓"] == True, "ID"].tolist()
        if selected_ids:
            st.info(f"Выбрано: **{len(selected_ids)}** вопросов")
            mc1, mc2, mc3, mc4 = st.columns(4)

            with mc1:
                new_topic = st.text_input("Новая тема", key="m_bulk_topic")
                if st.button("📁 Переместить", use_container_width=True, key="m_move"):
                    if new_topic.strip():
                        n = db.bulk_update_topic(selected_ids, new_topic.strip(), updated_by=st.session_state.user)
                        st.success(f"Перемещено: {n}")
                        st.rerun()

            with mc2:
                if st.button("🗄️ В архив", use_container_width=True, key="m_arch"):
                    n = db.bulk_delete_questions(selected_ids, deleted_by=st.session_state.user)
                    st.success(f"В архив: {n}")
                    st.rerun()

            with mc3:
                if st.button("♻️ Вернуть", use_container_width=True, key="m_restore"):
                    n = db.bulk_restore_questions(selected_ids, updated_by=st.session_state.user)
                    st.success(f"Восстановлено: {n}")
                    st.rerun()

            with mc4:
                ck = "m_confirm_hard_del"
                if st.session_state.get(ck) == tuple(selected_ids):
                    if st.button("⚠️ Удалить навсегда", type="primary", use_container_width=True, key="m_hd_ok"):
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

# ==================================================================
# ВКЛАДКА 2: РЕДАКТИРОВАНИЕ
# ==================================================================
with tab_edit:
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
                    e_opts.append(st.text_input(f"Вариант {CORRECT_LETTERS[i]}", value=o, key=f"m_eopt_{i}"))
            
            e_correct = st.selectbox(
                "Правильный ответ",
                options=range(len(e_opts)),
                format_func=lambda i: f"{CORRECT_LETTERS[i]}. {e_opts[i][:40]}",
                index=q["correct_answer"],
            )
            
            c1, c2 = st.columns(2)
            with c1:
                e_tags = st.text_input("Теги", value=q["tags"] or "")
            with c2:
                e_active = st.checkbox("Активен", value=bool(q["is_active"]))
            e_expl = st.text_area("Пояснение", value=q["explanation"] or "")

            c1, c2 = st.columns([1, 1])
            with c1:
                if st.form_submit_button("💾 Сохранить", type="primary", use_container_width=True):
                    db.update_question(
                        q["id"], topic=e_topic, question=e_question, options=e_opts,
                        correct_answer=e_correct, tags=e_tags or None,
                        explanation=e_expl or None, is_active=e_active, updated_by=st.session_state.user
                    )
                    del st.session_state["m_edit_q"]
                    st.success("Сохранено")
                    st.rerun()
            with c2:
                if st.form_submit_button("❌ Закрыть без сохранения", use_container_width=True):
                    del st.session_state["m_edit_q"]
                    st.rerun()
                    
    else:
        st.info("Выберите вопрос из списка ниже, чтобы отредактировать его.")
        
        with st.expander("🔍 Фильтры", expanded=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                topics = ["Все"] + db.get_all_topics(include_archived=True)
                f_topic = st.selectbox("Тема", topics, key="e_topic")
            with c2:
                f_search = st.text_input("Поиск по тексту/тегам", key="e_search")
            with c3:
                f_active = st.selectbox(
                    "Статус", ["Только активные", "Только архив", "Все"], key="e_active",
                )
            
            all_tags = db.get_all_tags()
            f_tag = st.selectbox("Фильтр по тегу", ["Все теги"] + all_tags, key="e_tag_filter")

        is_active_param = {"Только активные": True, "Только архив": False, "Все": None}[f_active]
        
        rows, total = db.get_questions_paginated(
            topic=f_topic,
            search=f_search or None,
            is_active=is_active_param,
            limit=100, 
            offset=0,
        )
        
        if f_tag != "Все теги":
            rows = [r for r in rows if r["tags"] and f_tag in r["tags"].split(",")]

        if not rows:
            st.warning("По вашим фильтрам ничего не найдено.")
        else:
            st.caption(f"Найдено: **{total}** вопросов (показаны первые 100)")
            
            q_options = {
                f"#{r['id']} [{r['topic']}] {r['question'][:60]}...": r["id"] 
                for r in reversed(rows)
            }
            
            selected_label = st.radio("Выберите вопрос", list(q_options.keys()), key="edit_radio_select")
            
            if st.button("📝 Загрузить для редактирования", type="primary"):
                selected_id = q_options[selected_label]
                st.session_state["m_edit_q"] = db.get_question_by_id(selected_id)
                st.rerun()

# ==================================================================
# ВКЛАДКА 3: НОВЫЙ ВОПРОС
# ==================================================================
with tab_add:
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
                        difficulty=1,
                        created_by=st.session_state.user,
                        tags=a_tags.strip() or None,
                        explanation=a_expl.strip() or None,
                    )
                    db.log_action(st.session_state.user_id, "question_add", f"Добавлен вопрос ID: {new_id}")
                    st.success(f"✅ Вопрос добавлен (ID: {new_id})")

# ==================================================================
# ВКЛАДКА 4: ИМПОРТ
# ==================================================================
with tab_import:
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
    uploaded = st.file_uploader("Выберите файл (CSV, JSON или Word)", type=["csv", "json", "docx"], key="m_up")

    if uploaded is not None:
        file_bytes = uploaded.read()
        fname = uploaded.name.lower()

        if fname.endswith(".csv"):
            questions, errors = parse_csv(file_bytes)
        elif fname.endswith(".json"):
            questions, errors = parse_json(file_bytes)
        elif fname.endswith(".docx"):
            from utils.import_word_questions import parse_questions_word
            questions, errors = parse_questions_word(file_bytes)
            if errors:
                st.error(errors)
                questions = []
        else:
            questions, errors = [], ["Поддерживаются только .csv, .json и .docx"]

        if errors:
            st.error(f"Найдено ошибок: **{len(errors)}**")
            with st.expander("Показать ошибки", expanded=True):
                for e in errors[:50]:
                    st.write("• " + e)

        if questions:
            st.success(f"✅ Валидных вопросов: **{len(questions)}**")

            with st.expander("Предпросмотр (первые 5)"):
                for q in questions[:5]:
                    # Выводим картинку, если она есть
                    if q.get("image_path") and os.path.exists(q["image_path"]):
                        st.image(q["image_path"], width=250)
                        
                    st.write(f"**{q['topic']}**: {q['question']}")
                    for i, o in enumerate(q["options"]):
                        mark = "✅" if i == q["correct_answer"] else "▫️"
                        st.write(f"  {mark} {CORRECT_LETTERS[i]}. {o}")
                    st.divider()

            if st.button(f"📥 Импортировать {len(questions)}", type="primary",
                         use_container_width=True, key="m_import_btn"):
                added, errs = db.bulk_add_questions(questions, created_by=st.session_state.user)
                db.log_action(st.session_state.user_id, "questions_import", f"Импортировано: {added} из {len(questions)}")
                
                if added > 0:
                    st.success(f"✅ Импортировано: **{added}** вопросов.")
                    if errs:
                        st.warning(f"С некоторыми вопросами возникли ошибки: {len(errs)}")
                        for e in errs[:20]:
                            st.write("• " + e)
                    
                    # Небольшая пауза, чтобы пользователь увидел сообщение об успехе
                    import time
                    time.sleep(1.5) 
                    
                    # Принудительное обновление страницы
                    st.rerun()
                else:
                    st.error("Не удалось импортировать вопросы.")
                    if errs:
                        for e in errs[:20]:
                            st.write("• " + e)

# ==================================================================
# ВКЛАДКА 5: ЭКСПОРТ
# ==================================================================
with tab_export:
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
# ВКЛАДКА 6: СТАТИСТИКА БАНКА
# ==================================================================
with tab_stats:
    if stats and stats.get("by_topic"):
        st.write("### 📚 По темам")
        df_topics = pd.DataFrame(stats["by_topic"])
        fig = px.bar(
            df_topics, x="topic", y="cnt", text="cnt",
            labels={"topic": "Тема", "cnt": "Кол-во вопросов"},
            color="cnt", color_continuous_scale="Blues",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            height=400, 
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.2)'),
            xaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            df_topics.rename(columns={
                "topic": "Тема", "cnt": "Вопросов",
                "archived": "В архиве",
            })[["Тема", "Вопросов", "В архиве"]],
            use_container_width=True, hide_index=True,
        )

    st.divider()
    st.subheader("📉 Анализ сложности вопросов (по ответам пользователей)")
    st.caption("Помогает выявить вопросы, на которые чаще всего отвечают неправильно.")

    q_stats = db.get_question_difficulty_stats()

    if not q_stats:
        st.info("Пока нет данных с ответами пользователей. Пройдите несколько тестов.")
    else:
        c1, c2 = st.columns([1, 2])
        with c1:
            stat_topics = ["Все темы"] + sorted(list(set(q["topic"] for q in q_stats)))
            stat_topic_filter = st.selectbox("Тема", stat_topics, key="stat_topic_filter")
        with c2:
            search_stat = st.text_input("Поиск по тексту вопроса", key="stat_search")

        filtered_stats = q_stats
        if stat_topic_filter != "Все темы":
            filtered_stats = [q for q in filtered_stats if q["topic"] == stat_topic_filter]
        if search_stat:
            filtered_stats = [q for q in filtered_stats if search_stat.lower() in q["question"].lower()]

        if not filtered_stats:
            st.warning("Нет вопросов по заданным фильтрам.")
        else:
            df_q_stats = pd.DataFrame([
                {
                    "ID": q["id"],
                    "Тема": q["topic"],
                    "Вопрос": q["question"][:60] + ("…" if len(q["question"]) > 60 else ""),
                    "Всего ответов": q["total_attempts"],
                    "Верных": q["correct_attempts"],
                    "Успешность": q["percentage"],
                }
                for q in filtered_stats
            ])

            st.dataframe(
                df_q_stats,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", width="small"),
                    "Успешность": st.column_config.ProgressColumn(
                        "Успешность", min_value=0, max_value=100, format="%.1f%%"
                    )
                }
            )

            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "📥 Скачать анализ в CSV",
                data=df_q_stats.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"question_stats_{ts}.csv",
                mime="text/csv",
            )

            st.info("💡 **Совет:** Вопросы с успешностью ниже 50% стоит пересмотреть.")