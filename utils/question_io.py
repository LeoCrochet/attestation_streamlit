"""Импорт/экспорт вопросов в CSV и JSON."""
import csv
import io
import json


REQUIRED_CSV_COLUMNS = [
    "topic", "question", "option_a", "option_b", "option_c", "option_d",
    "correct_answer",
]
OPTIONAL_CSV_COLUMNS = ["difficulty", "tags", "explanation"]
CORRECT_LETTERS = ["A", "B", "C", "D"]


def validate_question_dict(q, row_num=None):
    """Проверить словарь вопроса. Возвращает (ok, error_message)."""
    prefix = f"Строка {row_num}: " if row_num else ""

    for field in ("topic", "question"):
        if not q.get(field) or not str(q[field]).strip():
            return False, f"{prefix}поле '{field}' пустое"

    opts = q.get("options") or []
    if len(opts) < 2:
        return False, f"{prefix}нужно минимум 2 варианта ответа"
    if any(not str(o).strip() for o in opts):
        return False, f"{prefix}есть пустые варианты ответа"

    ca = q.get("correct_answer")
    try:
        ca_int = int(ca)
    except (TypeError, ValueError):
        return False, f"{prefix}'correct_answer' должен быть числом"
    if not (0 <= ca_int < len(opts)):
        return False, f"{prefix}'correct_answer' вне диапазона (0..{len(opts)-1})"

    try:
        diff = int(q.get("difficulty", 1))
    except (TypeError, ValueError):
        return False, f"{prefix}'difficulty' должен быть числом"
    if not (1 <= diff <= 5):
        return False, f"{prefix}'difficulty' должен быть 1..5"

    return True, None


def parse_csv(file_bytes):
    """Разобрать CSV-байты. Возвращает (questions, errors)."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("cp1251")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["Файл пуст или не содержит заголовков"]

    fieldnames = [f.strip() for f in reader.fieldnames]
    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in fieldnames]
    if missing:
        return [], [f"Отсутствуют обязательные колонки: {', '.join(missing)}"]

    questions = []
    errors = []

    for i, row in enumerate(reader, start=2):
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}

        correct_letter = str(row.get("correct_answer", "")).strip().upper()
        if correct_letter in CORRECT_LETTERS:
            correct_index = CORRECT_LETTERS.index(correct_letter)
        else:
            try:
                correct_index = int(correct_letter)
            except ValueError:
                errors.append(
                    f"Строка {i}: 'correct_answer' = '{correct_letter}' "
                    "— не A/B/C/D и не число"
                )
                continue

        q = {
            "topic": row.get("topic", ""),
            "question": row.get("question", ""),
            "options": [
                row.get("option_a", ""),
                row.get("option_b", ""),
                row.get("option_c", ""),
                row.get("option_d", ""),
            ],
            "correct_answer": correct_index,
            "difficulty": int(row.get("difficulty") or 1),
            "tags": row.get("tags") or None,
            "explanation": row.get("explanation") or None,
        }
        q["options"] = [o for o in q["options"] if o]

        ok, err = validate_question_dict(q, row_num=i)
        if not ok:
            errors.append(err)
            continue

        questions.append(q)

    return questions, errors


def parse_json(file_bytes):
    """Разобрать JSON-байты. Ожидается список вопросов."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("cp1251")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [], [f"Ошибка JSON: {e}"]

    if not isinstance(data, list):
        return [], ["Ожидался массив вопросов в корне JSON"]

    questions = []
    errors = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            errors.append(f"Элемент {i}: должен быть объектом")
            continue
        ok, err = validate_question_dict(item, row_num=i)
        if not ok:
            errors.append(err)
            continue
        questions.append(item)
    return questions, errors


def questions_to_csv(questions):
    """Сериализовать список вопросов в CSV-строку."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "topic", "question",
        "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "difficulty", "tags", "explanation",
    ])
    for q in questions:
        opts = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
        opts = (opts + ["", "", "", ""])[:4]
        ca = q["correct_answer"]
        ca_letter = CORRECT_LETTERS[ca] if 0 <= ca < 4 else ca
        writer.writerow([
            q.get("topic", ""),
            q.get("question", ""),
            opts[0], opts[1], opts[2], opts[3],
            ca_letter,
            q.get("difficulty", 1),
            q.get("tags", "") or "",
            q.get("explanation", "") or "",
        ])
    return output.getvalue()


def questions_to_json(questions):
    """Сериализовать список вопросов в JSON-строку."""
    result = []
    for q in questions:
        opts = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
        result.append({
            "topic": q.get("topic"),
            "question": q.get("question"),
            "options": opts,
            "correct_answer": q.get("correct_answer"),
            "difficulty": q.get("difficulty", 1),
            "tags": q.get("tags"),
            "explanation": q.get("explanation"),
        })
    return json.dumps(result, ensure_ascii=False, indent=2)


def build_csv_template():
    """Шаблон CSV с примерами."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "topic", "question",
        "option_a", "option_b", "option_c", "option_d",
        "correct_answer", "difficulty", "tags", "explanation",
    ])
    writer.writerow([
        "Python", "Что такое PEP 8?",
        "Стандарт оформления кода", "Версия Python",
        "Библиотека", "Среда разработки",
        "A", 1, "python,стиль", "PEP 8 — руководство по стилю Python",
    ])
    writer.writerow([
        "SQL", "Какой оператор выбирает данные?",
        "INSERT", "SELECT", "UPDATE", "DELETE",
        "B", 1, "sql,основы", "SELECT читает данные из таблиц",
    ])
    return output.getvalue()


def build_json_template():
    """Шаблон JSON с примером."""
    sample = [
        {
            "topic": "Python",
            "question": "Что такое PEP 8?",
            "options": [
                "Стандарт оформления кода", "Версия Python",
                "Библиотека", "Среда разработки",
            ],
            "correct_answer": 0,
            "difficulty": 1,
            "tags": "python,стиль",
            "explanation": "PEP 8 — руководство по стилю Python",
        },
    ]
    return json.dumps(sample, ensure_ascii=False, indent=2)