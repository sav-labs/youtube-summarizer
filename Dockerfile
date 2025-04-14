FROM python:3.9-slim

WORKDIR /app

# Установка необходимых зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . .

# Создание директории для логов и данных
RUN mkdir -p /app/logs

# Set PYTHONPATH to include the project root for proper imports
ENV PYTHONPATH=/app

# Запуск бота
CMD ["python", "src/app.py"] 