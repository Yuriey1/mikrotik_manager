"""
Вспомогательные функции
"""

def russian_to_mikrotik_comment(text):
    """
    Преобразует русские символы в формат MikroTik для комментариев.
    """
    result = []
    for char in text:
        if 'а' <= char.lower() <= 'я' or char == 'ё':
            result.append(char)
        else:
            result.append(char)
    return ''.join(result)
