#!/bin/bash

# Скрипт для деплоя YouTube Summarizer Bot
# Версия 2.0 с улучшенной обработкой ошибок и мониторингом

# Определение цветов для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Название Docker образа и контейнера
IMAGE_NAME="youtube-summarizer"
CONTAINER_NAME="youtube-summarizer-bot"
LOG_DIR="./logs"
DATA_DIR="./data"

# Функция для логирования
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    log "Проверка зависимостей..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен! Установите Docker и попробуйте снова."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker не запущен! Запустите Docker и попробуйте снова."
        exit 1
    fi
    
    log_success "Все зависимости в порядке"
}

# Создание необходимых директорий
create_directories() {
    log "Создание необходимых директорий..."
    
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR/config"
    mkdir -p "$DATA_DIR/temp"
    
    log_success "Директории созданы"
}

# Проверка конфигурации
check_configuration() {
    log "Проверка конфигурации..."
    
    if [ ! -f .env ]; then
        log_error "Файл .env не найден!"
        echo -e "Создайте файл .env на основе .env.example и заполните необходимые данные"
        exit 1
    fi
    
    # Проверка обязательных переменных
    source .env
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        log_error "TELEGRAM_BOT_TOKEN не задан в .env файле!"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        log_error "OPENAI_API_KEY не задан в .env файле!"
        exit 1
    fi
    
    log_success "Конфигурация корректна"
}

# Очистка старых Docker объектов
cleanup_docker() {
    log "Очистка старых Docker объектов..."
    
    # Остановка и удаление существующего контейнера
    if [ "$(docker ps -a -f name=$CONTAINER_NAME -q)" ]; then
        log "Останавливаю существующий контейнер..."
        docker stop $CONTAINER_NAME
        docker rm $CONTAINER_NAME
        log_success "Существующий контейнер удален"
    fi
    
    # Удаление неиспользуемых образов
    docker image prune -f --filter="label!=keep" > /dev/null 2>&1
    
    log_success "Очистка завершена"
}

# Сборка Docker образа
build_image() {
    log "Сборка Docker образа..."
    
    docker build -t $IMAGE_NAME . --no-cache
    
    if [ $? -ne 0 ]; then
        log_error "Ошибка при сборке Docker образа!"
        exit 1
    fi
    
    log_success "Docker образ успешно собран"
}

# Запуск контейнера
start_container() {
    log "Запуск нового контейнера..."
    
    docker run -d \
        --name $CONTAINER_NAME \
        --restart unless-stopped \
        --env-file .env \
        -v $(pwd)/logs:/app/logs \
        -v $(pwd)/data:/app/data \
        $IMAGE_NAME
    
    if [ $? -ne 0 ]; then
        log_error "Ошибка при запуске контейнера!"
        exit 1
    fi
    
    log_success "Контейнер успешно запущен"
}

# Проверка состояния контейнера
check_container_health() {
    log "Проверка состояния контейнера..."
    
    sleep 5  # Ждем пока контейнер запустится
    
    if [ "$(docker ps -f name=$CONTAINER_NAME -q)" ]; then
        log_success "Контейнер работает"
        
        # Проверяем логи на наличие ошибок
        if docker logs $CONTAINER_NAME --tail 10 | grep -q "ERROR\|CRITICAL"; then
            log_warning "Обнаружены ошибки в логах. Проверьте логи контейнера:"
            echo "docker logs $CONTAINER_NAME"
        else
            log_success "Логи выглядят нормально"
        fi
    else
        log_error "Контейнер не запущен!"
        echo "Проверьте логи для диагностики:"
        echo "docker logs $CONTAINER_NAME"
        exit 1
    fi
}

# Показать полезную информацию
show_info() {
    echo ""
    echo -e "${GREEN}===========================================${NC}"
    echo -e "${GREEN}  Деплой завершен успешно!${NC}"
    echo -e "${GREEN}===========================================${NC}"
    echo ""
    echo -e "${YELLOW}Полезные команды:${NC}"
    echo -e "  Просмотр логов:     ${BLUE}docker logs -f $CONTAINER_NAME${NC}"
    echo -e "  Остановка бота:     ${BLUE}docker stop $CONTAINER_NAME${NC}"
    echo -e "  Запуск бота:        ${BLUE}docker start $CONTAINER_NAME${NC}"
    echo -e "  Перезапуск бота:    ${BLUE}docker restart $CONTAINER_NAME${NC}"
    echo -e "  Статус контейнера:  ${BLUE}docker ps -f name=$CONTAINER_NAME${NC}"
    echo -e "  Удаление контейнера:${BLUE}docker rm -f $CONTAINER_NAME${NC}"
    echo ""
    echo -e "${YELLOW}Файлы проекта:${NC}"
    echo -e "  Логи:               ${BLUE}./logs/${NC}"
    echo -e "  Данные:             ${BLUE}./data/${NC}"
    echo -e "  Конфигурация:       ${BLUE}./.env${NC}"
    echo ""
}

# Основная функция
main() {
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}  YouTube Summarizer Bot - Деплой v2.0${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    echo ""
    
    check_dependencies
    create_directories
    check_configuration
    cleanup_docker
    build_image
    start_container
    check_container_health
    show_info
}

# Обработка Ctrl+C
trap 'echo -e "\n${RED}Деплой прерван пользователем${NC}"; exit 1' INT

# Запуск основной функции
main 