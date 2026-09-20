"""Формирование протоколов тестирования."""
import io
from datetime import datetime

import pandas as pd


def build_group_report_dataframe(stats_rows):
    """Из сводки группы сделать DataFrame для отображения/экспорта."""
    data = []
    for r in stats_rows:
        data.append({
            "ФИО": r.get("full_name") or r.get("username"),
            "Логин": r.get("username"),
            "Тестов": r.get("tests_count") or 0,
            "Средний балл %": round(r.get("avg_score") or 0, 1),
            "Лучший %": round(r.get("max_score") or 0, 1),
            "Правильных": r.get("total_correct") or 0,
            "Всего вопросов": r.get("total_questions") or 0,
            "Последний тест": (
                r["last_test_date"].strftime("%d.%m.%Y %H:%M")
                if r.get("last_test_date") else "—"
            ),
        })
    return pd.DataFrame(data)


def build_protocol_dataframe(group_name, topic, detailed_rows):
    """
    Детальный протокол: по каждому студенту — последний/все результаты.
    """
    data = []
    for i, r in enumerate(detailed_rows, start=1):
        data.append({
            "№": i,
            "ФИО": r.get("full_name") or r.get("username"),
            "Логин": r.get("username"),
            "Дата": r["date"].strftime("%d.%m.%Y %H:%M") if r.get("date") else "—",
            "Тема": r.get("topic") or "—",
            "Правильных": r.get("score"),
            "Всего": r.get("total_questions"),
            "Результат %": round(r.get("percentage") or 0, 1),
            "Время, сек": r.get("time_spent") or "—",
        })
    return pd.DataFrame(data)


def dataframe_to_csv_bytes(df):
    """DataFrame → байты CSV (utf-8-sig для Excel)."""
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_to_excel_bytes(df, sheet_name="Протокол", header_info=None):
    """
    DataFrame → Excel-файл в памяти.
    header_info: dict {group: str, topic: str, date: str} — шапка над таблицей.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if header_info:
            # Сначала пишем шапку, потом таблицу с отступом
            info_df = pd.DataFrame([
                ["Протокол тестирования"],
                [""],
                ["Группа:", header_info.get("group", "—")],
                ["Тема:", header_info.get("topic", "Все темы")],
                ["Дата формирования:", header_info.get("date",
                    datetime.now().strftime("%d.%m.%Y %H:%M"))],
                [""],
            ])
            info_df.to_excel(writer, sheet_name=sheet_name,
                             index=False, header=False, startrow=0)
            df.to_excel(writer, sheet_name=sheet_name, index=False,
                        startrow=len(info_df) + 1)
        else:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output.getvalue()