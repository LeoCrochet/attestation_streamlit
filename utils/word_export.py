import io
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def generate_answers_word(user_name, topic, score, total, answers_data):
    """
    Генерирует Word-документ с детальным разбором ответов.
    """
    doc = Document()
    
    # Заголовок
    title = doc.add_heading('Детальный разбор ответов', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Информация о тесте
    p = doc.add_paragraph()
    p.add_run(f'Студент: ').bold = True
    p.add_run(user_name)
    
    p = doc.add_paragraph()
    p.add_run(f'Тема: ').bold = True
    p.add_run(topic)
    
    p = doc.add_paragraph()
    p.add_run(f'Результат: ').bold = True
    p.add_run(f'{score} из {total}')
    
    doc.add_paragraph('_' * 50)

    # Разбор вопросов
    for i, ans in enumerate(answers_data, start=1):
        # Вопрос
        q_para = doc.add_paragraph()
        q_para.add_run(f'Вопрос {i}: ').bold = True
        q_para.add_run(ans.get("question_text", "—"))
        
        # Варианты ответов
        opts = ans.get("options", [])
        user_idx = ans.get("user_answer_idx")
        correct_idx = ans.get("correct_answer_idx")
        
        for opt_i, opt_text in enumerate(opts):
            is_user_choice = (opt_i == user_idx)
            is_correct = (opt_i == correct_idx)
            
            opt_para = doc.add_paragraph(style='List Bullet')
            
            if is_correct and is_user_choice:
                run = opt_para.add_run(f"{chr(65 + opt_i)}. {opt_text} (Ваш ответ, верно)")
                run.font.color.rgb = RGBColor(0, 128, 0) # Зеленый
            elif is_correct:
                run = opt_para.add_run(f"{chr(65 + opt_i)}. {opt_text} (Правильный ответ)")
                run.font.color.rgb = RGBColor(0, 128, 0) # Зеленый
            elif is_user_choice:
                run = opt_para.add_run(f"{chr(65 + opt_i)}. {opt_text} (Ваш ответ, неверно)")
                run.font.color.rgb = RGBColor(255, 0, 0) # Красный
            else:
                opt_para.add_run(f"{chr(65 + opt_i)}. {opt_text}")
        
        doc.add_paragraph('-' * 30)

    # Сохраняем в буфер
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()