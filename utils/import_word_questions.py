"""Парсер вопросов с поддержкой таблиц и картинок."""
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
    image_paths = {}
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            ext = rel.target_ref.split('.')[-1]
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = f"uploads/questions/{filename}"
            with open(filepath, "wb") as f:
                f.write(rel.target_part.blob)
            image_paths[rel.rId] = filepath

    # 2. Собираем текст и таблицы
    full_text = []
    table_options = {}
    
    for element in doc.element.body:
        if element.tag.endswith('p'):
            text = "".join(node.text for node in element.iter() if node.tag.endswith('t') and node.text)
            if text.strip():
                full_text.append(text.strip())
        elif element.tag.endswith('tbl'):
            tbl = next((t for t in doc.tables if t._tbl == element), None)
            if tbl:
                opts = []
                for row in tbl.rows:
                    cells = row.cells
                    if len(cells) >= 2:
                        letter_text = cells[0].text.strip()
                        # Ищем картинку во второй ячейке
                        img_rIds = re.findall(r'r:embed="(rId\d+)"', cells[1]._tc.xml)
                        img_path = None
                        if img_rIds and img_rIds[0] in image_paths:
                            img_path = image_paths[img_rIds[0]]
                        
                        letter_match = re.match(r'^([AАБВГ])', letter_text)
                        if letter_match:
                            letter = letter_match.group(1).upper().replace('A', 'А').replace('B', 'Б')
                            opts.append({"letter": letter, "text": letter_text, "image_path": img_path})
                
                table_key = f"TABLE_{len(table_options)}"
                table_options[table_key] = opts
                full_text.append(f" [{table_key}] ")

    text = " ".join(full_text)
    text = text.replace('\xa0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'[•●○■□▪▫►▶]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 3. ПРАВИЛЬНЫЕ ОТВЕТЫ (Ищем в полном тексте ДО обрезки)
    answers_dict = {}
    tail_text = text[-1500:] # Берем последние 1500 символов
    # Ищем паттерн: цифра, пробел, буква (например, "1 А", "2 В")
    matches = re.findall(r'(\d{1,2})\s*[\.\,]?\s*([AАБВГ](?:[\s\,\.]*[AАБВГ])*)', tail_text)
    
    for q_num, ans_letters in matches:
        ans_letters = ans_letters.upper().replace('A', 'А').replace('B', 'Б').replace('C', 'В')
        # Очищаем от лишних символов (точек, запятых)
        ans_letters = re.sub(r'[^АБВГ]', '', ans_letters)
        answers_dict[int(q_num)] = ans_letters

    # 4. ОБРЕЗАЕМ ХВОСТ (Чтобы мусор не попал в вопросы)
    cut_markers = ["***Конец", "СПАСИБО ЗА УЧАСТИЕ", "Правильные ответы", "Результат_______"]
    for marker in cut_markers:
        if marker in text:
            text = text.split(marker)[0].strip()
            break 

    # 5. РАЗБИВАЕМ НА ВОПРОСЫ
    final_questions = []
    question_starts = list(re.finditer(r'(?<!\d)(\d{1,2})\.', text))
    
    if not question_starts:
        return None, "Не найдено ни одного вопроса."

    for i in range(len(question_starts)):
        start_match = question_starts[i]
        q_num = int(start_match.group(1))
        
        start_idx = start_match.start()
        end_idx = question_starts[i+1].start() if i + 1 < len(question_starts) else len(text)
        
        q_block = text[start_idx:end_idx].strip()
        q_block = re.sub(r'^\d{1,2}\.\s*', '', q_block).strip()
        
        if len(q_block) < 10:
            continue

        opts = []
        table_match = re.search(r'\[(TABLE_\d+)\]', q_block)
        if table_match:
            table_key = table_match.group(1)
            if table_key in table_options:
                opts = table_options[table_key]
                q_block = q_block.replace(table_match.group(0), "").strip()
        
        if not opts:
            opt_parts = re.split(r'(?=\b[AАБВГ][\)\.])', q_block)
            if len(opt_parts) >= 3:
                question_text = opt_parts[0].strip()
                for opt_part in opt_parts[1:]:
                    opt_match = re.match(r'^([AАБВГ])[\)\.]\s*(.*)', opt_part.strip(), re.DOTALL)
                    if opt_match:
                        letter = opt_match.group(1).upper().replace('A', 'А').replace('B', 'Б').replace('C', 'В')
                        opt_text = re.sub(r'\s+', ' ', opt_match.group(2)).strip()
                        opts.append({"letter": letter, "text": opt_text, "image_path": None})
            else:
                continue
        else:
            question_text = q_block.strip()

        if len(opts) < 2:
            continue

        correct_indices = []
        correct_letters_str = answers_dict.get(q_num, "")
        
        if correct_letters_str:
            for letter in correct_letters_str:
                for j, opt in enumerate(opts):
                    if opt["letter"] == letter:
                        correct_indices.append(j)
                        break
                        
        if not correct_indices:
            correct_indices = [0]

        final_questions.append({
            "topic": "Импорт из Word",
            "question": question_text,
            "options": [opt["text"] for opt in opts],
            "option_images": [opt["image_path"] for opt in opts],
            "correct_answer": correct_indices,
            "explanation": None,
            "tags": None,
            "image_path": None
        })

    return final_questions, None