"""Парсер заявок в формате Word (.docx)."""
import io
import re
from docx import Document

def _extract_meta(doc):
    org_name = None
    contact_person = None
    
    # Собираем весь текст в одну строку (с пробелами вместо переносов)
    full_text = " ".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    
    # 1. Поиск организации
    # Ищем "Название организации...", затем любые символы (включая скобки), 
    # затем извлекаем текст до подчеркиваний или слов "Юридический/Почтовый"
    org_match = re.search(
        r'Название организации.*?(?:\)|\s|:)?\s*([А-ЯЁа-яёA-Za-z0-9\s«»"\'-]+?)(?=_|Юридический|Почтовый|Телефон|E-mail|$)', 
        full_text, 
        re.IGNORECASE
    )
    if org_match:
        org_name = org_match.group(1).strip()
    
    # 2. Поиск контактного лица
    # Ищем "Контактное лицо", затем "ФИО", затем извлекаем текст (буквы, точки, пробелы) до "тел." или цифр
    contact_match = re.search(
        r'Контактное лицо.*?ФИО\s*([А-ЯЁа-яёA-Za-z\s\.]+?)(?=тел\.|\d|$)', 
        full_text, 
        re.IGNORECASE
    )
    if contact_match:
        contact_person = contact_match.group(1).strip()

    return org_name, contact_person


def parse_application_word(file_bytes):
    """
    Парсит Word-документ. Возвращает (data, meta, error).
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        return None, None, f"Ошибка чтения Word: {e}"

    org_name, contact_person = _extract_meta(doc)
    meta = {
        "organization": org_name,
        "contact_person": contact_person
    }

    # Ищем таблицу с сотрудниками
    target_table = None
    for table in doc.tables:
        header_text = ""
        if table.rows:
            for cell in table.rows[0].cells:
                header_text += cell.text.lower() + " "
            
        if "фио" in header_text and ("профессия" in header_text or "образование" in header_text):
            target_table = table
            break

    if not target_table:
        return None, meta, "В документе не найдена таблица с колонками 'ФИО' и 'Профессия'."

    headers = [cell.text.strip().lower() for cell in target_table.rows[0].cells]
    
    def get_idx(keywords):
        if isinstance(keywords, str):
            keywords = [keywords]
        for i, h in enumerate(headers):
            for kw in keywords:
                if kw in h:
                    return i
        return None

    idx_fio = get_idx("фио")
    idx_prof_current = get_idx(["профессия в настоящее", "профессия (разряд)", "профессия"])
    idx_edu = get_idx("образование")
    idx_year = get_idx("год рождения")
    idx_prof_target = get_idx(["профессия (направление)", "направление", "курс"])
    idx_type = get_idx(["вид обучения", "вид проверки"])

    if idx_fio is None:
        return None, meta, "Не найдена колонка 'ФИО' в таблице."

    parsed_data = []

    for row in target_table.rows[1:]:
        cells = row.cells
        
        def get_text(idx):
            if idx is not None and idx < len(cells):
                txt = cells[idx].text.strip()
                txt = re.sub(r'\s+', ' ', txt).strip()
                return txt if txt and txt != "—" else None
            return None

        fio = get_text(idx_fio)
        
        if not fio or fio.isdigit():
            continue

        birth_year = None
        year_str = get_text(idx_year)
        if year_str:
            match = re.search(r'\d{4}', year_str)
            if match:
                birth_year = int(match.group())

        profession = get_text(idx_prof_target) or get_text(idx_prof_current)
        training_type = get_text(idx_type) or "Первичное"

        parsed_data.append({
            "fio": fio,
            "profession": profession,
            "education": get_text(idx_edu),
            "birth_year": birth_year,
            "training_type": training_type
        })

    if not parsed_data:
        return None, meta, "Таблица найдена, но в ней нет заполненных строк с ФИО."

    return parsed_data, meta, None