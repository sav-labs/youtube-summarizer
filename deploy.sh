#!/bin/bash

# Скрипт для деплоя YouTube Summarizer Bot

# Определение цветов для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Название Docker образа и контейнера
IMAGE_NAME="youtube-summarizer"
CONTAINER_NAME="youtube-summarizer-bot"

echo -e "${YELLOW}Начинаю процесс деплоя YouTube Summarizer Bot${NC}"

# Проверка наличия файла .env
if [ ! -f .env ]; then
  echo -e "${RED}Ошибка: Файл .env не найден!${NC}"
  echo -e "Создайте файл .env на основе .env.example и заполните необходимые данные"
  exit 1
fi

echo -e "${GREEN}Файл .env найден${NC}"

# Сборка Docker образа
echo -e "${YELLOW}Сборка Docker образа...${NC}"
docker build -t $IMAGE_NAME .

if [ $? -ne 0 ]; then
  echo -e "${RED}Ошибка при сборке Docker образа!${NC}"
  exit 1
fi

echo -e "${GREEN}Docker образ успешно собран${NC}"

# Остановка и удаление существующего контейнера, если он есть
if [ "$(docker ps -a | grep $CONTAINER_NAME)" ]; then
  echo -e "${YELLOW}Останавливаю существующий контейнер...${NC}"
  docker stop $CONTAINER_NAME
  docker rm $CONTAINER_NAME
  echo -e "${GREEN}Существующий контейнер остановлен и удален${NC}"
fi

# Запуск нового контейнера
echo -e "${YELLOW}Запускаю новый контейнер...${NC}"
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  $IMAGE_NAME

if [ $? -ne 0 ]; then
  echo -e "${RED}Ошибка при запуске контейнера!${NC}"
  exit 1
fi

echo -e "${GREEN}Контейнер успешно запущен!${NC}"
echo -e "${YELLOW}Для просмотра логов выполните: ${NC}docker logs -f $CONTAINER_NAME"
echo -e "${GREEN}Деплой завершен успешно${NC}" 