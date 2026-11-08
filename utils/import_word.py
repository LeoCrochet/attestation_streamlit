"""Парсер заявок в формате Word (.docx)."""
import io
import re
from docx import Document

def parse_application_word(file_bytes):
    """
    Парсит Word-документ, находит главную таблицу со списком сотрудников.
    Ожидает колонки: ФИО, Профессия и т.д.
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        return None, f"Ошибка чтения Word: {e}"

    # Ищем таблицу, в которой есть слова "ФИО" и "Профессия"
    target_table = None
    for table in doc.tables:
        header_text = ""
        if table.rows:
            for cell in table.rows[0].cells:
                header_text += cell.text.lower() + " "
            
        if "фио" in header_text:
            target_table = table
            break

    if not target_table:
        return None, "В документе не найдена таблица с колонкой 'ФИО'."

    # Определяем индексы колонок по заголовкам
    headers = [cell.text.strip().lower() for cell in target_table.rows[0].cells]
    
    def get_idx(keyword):
        for i, h in enumerate(headers):
            if keyword in h:
                return i
        return None

    idx_fio = get_idx("фио")
    idx_prof = get_idx("профессия")
    idx_edu = get_idx("образование")
    idx_year = get_idx("год рождения")
    idx_type = get_idx("вид обучения")

    if idx_fio is None:
        return None, "Не найдена колонка 'ФИО' в таблице."

    parsed_data = []

    # Проходим по строкам, пропуская заголовок
    for row in target_table.rows[1:]:
        cells = row.cells
        
        def get_text(idx):
            if idx is not None and idx < len(cells):
                txt = cells[idx].text.strip()
                return txt if txt and txt != "—" else None
            return None

        fio = get_text(idx_fio)
        if not fio:
            continue # Пропускаем пустые строки

        birth_year = None
        year_str = get_text(idx_year)
        if year_str:
            match = re.search(r'\d{4}', year_str)
            if match:
                birth_year = int(match.group())

        parsed_data.append({
            "fio": fio,
            "profession": get_text(idx_prof),
            "education": get_text(idx_edu),
            "birth_year": birth_year,
            "training_type": get_text(idx_type) or "Первичное"
        })

    return parsed_data, None