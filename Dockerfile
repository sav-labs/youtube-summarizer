FROM python:3.9-slim

WORKDIR /app

# Установка необходимых зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . .

# Создание директории для логов
RUN mkdir -p /app/logs

# Запуск бота
CMD ["python", "src/bot.py"] 