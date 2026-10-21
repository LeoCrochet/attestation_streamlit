import io
import pandas as pd

def parse_application_excel(file_bytes):
    """
    Парсит Excel/CSV файл с заявкой.
    Ожидаемые колонки: ФИО, Профессия, Образование, Год рождения, Вид обучения.
    """
    try:
        # Читаем Excel или CSV (поддерживаем оба формата)
        if file_bytes[:2] == b'PK': # Признак zip-архива (Excel)
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=';', encoding='utf-8-sig')
    except Exception as e:
        return None, f"Ошибка чтения файла: {e}"

    # Приводим названия колонок к нижнему регистру для надежности
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Проверяем обязательные колонки
    if "фио" not in df.columns:
        return None, "В файле нет колонки 'ФИО'"

    parsed_data = []
    
    # Вспомогательная функция для безопасного извлечения строк
    def safe_str(val):
        if pd.isna(val):
            return None
        s = str(val).strip()
        return s if s else None

    for idx, row in df.iterrows():
        fio = safe_str(row.get("фио"))
        if not fio:
            continue # Пропускаем пустые строки

        # Извлекаем данные
        profession = safe_str(row.get("профессия"))
        education = safe_str(row.get("образование"))
        
        birth_year = None
        if "год рождения" in df.columns and not pd.isna(row.get("год рождения")):
            try:
                birth_year = int(row.get("год рождения"))
            except ValueError:
                pass
                
        training_type = safe_str(row.get("вид обучения"))
        if not training_type:
            training_type = "Первичное"

        parsed_data.append({
            "fio": fio,
            "profession": profession,
            "education": education,
            "birth_year": birth_year,
            "training_type": training_type
        })

    return parsed_data, None