"""Надежный парсер вопросов из Word (.docx) с автоопределением темы."""
import io
import re
import os
import uuid
from docx import Document

def parse_questions_word(file_bytes):
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        return None, f"Ошибка чтения Word: {e}"

    os.makedirs("uploads/questions", exist_ok=True)

    # 1. Извлекаем картинки
    image_list = []
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            ext = rel.target_ref.split('.')[-1]
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = f"uploads/questions/{filename}"
            with open(filepath, "wb") as f:
                f.write(rel.target_part.blob)
            image_list.append(filepath)

    # 2. Собираем текст и ищем заголовок
    full_text = []
    auto_topic = "Импорт из Word" # Тема по умолчанию
    
    for p in doc.paragraphs:
        if p.text.strip():
            text = p.text.strip()
            full_text.append(text)
            
            # Ищем заголовок темы (если тема еще не найдена)
            # Обычно он начинается со слова "Тест" или "Тема:"
            if auto_topic == "Импорт из Word":
                if text.lower().startswith("тест для") or text.lower().startswith("тест по"):
                    # Очищаем от лишних кавычек и пробелов
                    auto_topic = text.strip('"\'«» ').strip()
                elif text.lower().startswith("тема:"):
                    auto_topic = text[5:].strip('"\'«» ').strip()

    # Добавляем текст из таблиц
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    full_text.append(cell.text.strip())

    text = " ".join(full_text)
    text = text.replace('\xa0', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)

    # Обрезаем тему, если она слишком длинная (для красоты в БД)
    if len(auto_topic) > 100:
        auto_topic = auto_topic[:97] + "..."

    # 3. Ищем ответы
    answers_dict = {}
    tail_text = text[-1000:]
    matches = re.findall(r'(\d{1,2})\s*([AАБВГ](?:\s*,\s*[AАБВГ])*)', tail_text)
    for q_num, ans_letters in matches:
        ans_letters = ans_letters.upper().replace('A', 'А').replace('B', 'Б').replace('C', 'В')
        answers_dict[int(q_num)] = ans_letters

    # 4. Разбиваем на вопросы
    final_questions = []
    question_starts = list(re.finditer(r'(?<!\d)(\d{1,2})[\.\)]\s+', text))
    
    if not question_starts:
        return None, f"Не найдено ни одного вопроса. Начало текста: {text[:200]}..."

    img_index = 0

    for i in range(len(question_starts)):
        start_match = question_starts[i]
        q_num = int(start_match.group(1))
        
        start_idx = start_match.start()
        end_idx = question_starts[i+1].start() if i + 1 < len(question_starts) else len(text)
        
        q_block = text[start_idx:end_idx].strip()
        q_block = re.sub(r'^\d{1,2}[\.\)]\s+', '', q_block).strip()
        
        if len(q_block) < 10:
            continue

        opt_parts = re.split(r'(?=\b[AАБВГ][\)\.])', q_block)
        
        if len(opt_parts) < 3:
            continue

        question_text = opt_parts[0].strip()
        
        opts = []
        for opt_part in opt_parts[1:]:
            opt_part = opt_part.strip()
            opt_match = re.match(r'^([AАБВГ])[\)\.]\s*(.*)', opt_part, re.DOTALL)
            if opt_match:
                letter = opt_match.group(1).upper().replace('A', 'А').replace('B', 'Б').replace('C', 'В')
                opt_text = opt_match.group(2).strip()
                opts.append({"letter": letter, "text": opt_text})
        
        if len(opts) < 2:
            continue

        image_path = None
        if img_index < len(image_list):
            image_path = image_list[img_index]
            img_index += 1

        correct_idx = 0
        correct_letter = answers_dict.get(q_num, "")
        if correct_letter:
            first_letter = correct_letter[0]
            for j, opt in enumerate(opts):
                if opt["letter"] == first_letter:
                    correct_idx = j
                    break

        final_questions.append({
            "topic": auto_topic, # <-- ТЕПЕРЬ ИСПОЛЬЗУЕМ АВТОТЕМУ
            "question": question_text,
            "options": [opt["text"] for opt in opts],
            "correct_answer": correct_idx,
            "explanation": None,
            "tags": None,
            "image_path": image_path
        })

    if not final_questions:
        return None, f"Найдено {len(question_starts)} номеров, но не удалось собрать вопросы с вариантами."
        
    return final_questions, None