#!/bin/bash
set -e

# Название приложения и контейнера
APP_NAME="youtube-summarizer-bot"
CONTAINER_NAME="youtube-summarizer-bot"

echo "🚀 Начинаем деплой YouTube Summarizer бота..."

# Остановка и удаление существующего контейнера (если есть)
echo "Останавливаю и удаляю существующий контейнер..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Удаление старого образа
echo "Удаляю старый образ..."
docker rmi $APP_NAME:latest 2>/dev/null || true

# Сборка нового образа
echo "Собираю новый Docker-образ..."
docker build --no-cache -t $APP_NAME:latest .

# Проверка наличия файла .env
if [ ! -f .env ]; then
    echo "ОШИБКА: Файл .env не найден!"
    echo "Создайте файл .env с переменными TELEGRAM_BOT_TOKEN и OPENAI_API_KEY"
    exit 1
fi

# Запуск нового контейнера
echo "Запускаю новый контейнер..."
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    --env-file .env \
    -v $(pwd)/logs:/app/logs \
    $APP_NAME:latest

# Вывод статуса
echo "Статус контейнера:"
docker ps -a --filter "name=$CONTAINER_NAME"
echo ""
echo "Последние 10 строк логов:"
sleep 3
docker logs -n 10 $CONTAINER_NAME

echo "✅ Деплой успешно завершен!"
echo "📋 Логи можно посмотреть командой: docker logs -f $CONTAINER_NAME" 