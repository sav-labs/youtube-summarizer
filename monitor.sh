#!/bin/bash

# Скрипт мониторинга YouTube Summarizer Bot
# Показывает состояние контейнера, логи и статистику

# Определение цветов для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONTAINER_NAME="youtube-summarizer-bot"

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

# Проверка статуса контейнера
check_container_status() {
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}  Статус контейнера${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    
    if [ "$(docker ps -f name=$CONTAINER_NAME -q)" ]; then
        log_success "Контейнер запущен и работает"
        
        # Показываем информацию о контейнере
        echo ""
        echo -e "${BLUE}Информация о контейнере:${NC}"
        docker ps -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        
        # Показываем использование ресурсов
        echo ""
        echo -e "${BLUE}Использование ресурсов:${NC}"
        docker stats $CONTAINER_NAME --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
        
    else
        log_error "Контейнер не запущен!"
        
        # Проверяем, существует ли контейнер
        if [ "$(docker ps -a -f name=$CONTAINER_NAME -q)" ]; then
            log_warning "Контейнер существует, но остановлен"
            echo ""
            echo -e "${BLUE}Статус остановленного контейнера:${NC}"
            docker ps -a -f name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}"
        else
            log_error "Контейнер не существует!"
        fi
    fi
}

# Показать последние логи
show_logs() {
    echo ""
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}  Последние 20 строк логов${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    
    if [ "$(docker ps -a -f name=$CONTAINER_NAME -q)" ]; then
        docker logs $CONTAINER_NAME --tail 20
    else
        log_error "Контейнер не существует!"
    fi
}

# Анализ логов на ошибки
analyze_logs() {
    echo ""
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}  Анализ логов на ошибки${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    
    if [ "$(docker ps -a -f name=$CONTAINER_NAME -q)" ]; then
        # Ищем ошибки в логах
        error_count=$(docker logs $CONTAINER_NAME 2>&1 | grep -c "ERROR\|CRITICAL")
        warning_count=$(docker logs $CONTAINER_NAME 2>&1 | grep -c "WARNING")
        
        echo -e "${BLUE}Количество ошибок:${NC} $error_count"
        echo -e "${BLUE}Количество предупреждений:${NC} $warning_count"
        
        if [ $error_count -gt 0 ]; then
            echo ""
            echo -e "${RED}Последние ошибки:${NC}"
            docker logs $CONTAINER_NAME 2>&1 | grep "ERROR\|CRITICAL" | tail -5
        fi
        
        if [ $warning_count -gt 0 ]; then
            echo ""
            echo -e "${YELLOW}Последние предупреждения:${NC}"
            docker logs $CONTAINER_NAME 2>&1 | grep "WARNING" | tail -3
        fi
        
        if [ $error_count -eq 0 ] && [ $warning_count -eq 0 ]; then
            log_success "Ошибок и предупреждений не обнаружено"
        fi
    else
        log_error "Контейнер не существует!"
    fi
}

# Показать полезные команды
show_commands() {
    echo ""
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}  Полезные команды управления${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    echo ""
    echo -e "${BLUE}Основные команды:${NC}"
    echo -e "  Просмотр логов в реальном времени: ${GREEN}docker logs -f $CONTAINER_NAME${NC}"
    echo -e "  Перезапуск бота:                   ${GREEN}docker restart $CONTAINER_NAME${NC}"
    echo -e "  Остановка бота:                    ${GREEN}docker stop $CONTAINER_NAME${NC}"
    echo -e "  Запуск бота:                       ${GREEN}docker start $CONTAINER_NAME${NC}"
    echo -e "  Удаление контейнера:               ${GREEN}docker rm -f $CONTAINER_NAME${NC}"
    echo ""
    echo -e "${BLUE}Диагностика:${NC}"
    echo -e "  Войти в контейнер:                 ${GREEN}docker exec -it $CONTAINER_NAME /bin/sh${NC}"
    echo -e "  Статистика ресурсов:               ${GREEN}docker stats $CONTAINER_NAME${NC}"
    echo -e "  Размер логов:                      ${GREEN}docker logs $CONTAINER_NAME 2>&1 | wc -l${NC}"
    echo ""
}

# Интерактивное меню
interactive_menu() {
    while true; do
        echo ""
        echo -e "${YELLOW}===========================================${NC}"
        echo -e "${YELLOW}  YouTube Summarizer Bot - Мониторинг${NC}"
        echo -e "${YELLOW}===========================================${NC}"
        echo ""
        echo "Выберите действие:"
        echo "1) Проверить статус контейнера"
        echo "2) Показать последние логи"
        echo "3) Анализ логов на ошибки"
        echo "4) Следить за логами в реальном времени"
        echo "5) Перезапустить бот"
        echo "6) Показать полезные команды"
        echo "0) Выход"
        echo ""
        read -p "Ваш выбор: " choice
        
        case $choice in
            1)
                check_container_status
                ;;
            2)
                show_logs
                ;;
            3)
                analyze_logs
                ;;
            4)
                echo -e "${BLUE}Следим за логами (Ctrl+C для выхода):${NC}"
                docker logs -f $CONTAINER_NAME
                ;;
            5)
                echo -e "${BLUE}Перезапускаю контейнер...${NC}"
                docker restart $CONTAINER_NAME
                if [ $? -eq 0 ]; then
                    log_success "Контейнер перезапущен"
                else
                    log_error "Ошибка при перезапуске контейнера"
                fi
                ;;
            6)
                show_commands
                ;;
            0)
                echo -e "${GREEN}До свидания!${NC}"
                exit 0
                ;;
            *)
                log_error "Неверный выбор. Попробуйте снова."
                ;;
        esac
        
        echo ""
        read -p "Нажмите Enter для продолжения..."
    done
}

# Основная функция
main() {
    # Проверяем аргументы командной строки
    case "${1:-}" in
        "status")
            check_container_status
            ;;
        "logs")
            show_logs
            ;;
        "errors")
            analyze_logs
            ;;
        "commands")
            show_commands
            ;;
        "")
            # Если аргументов нет, показываем интерактивное меню
            interactive_menu
            ;;
        *)
            echo "Использование: $0 [status|logs|errors|commands]"
            echo "Без аргументов запускается интерактивное меню"
            exit 1
            ;;
    esac
}

# Обработка Ctrl+C
trap 'echo -e "\n${YELLOW}Мониторинг остановлен${NC}"; exit 0' INT

# Запуск основной функции
main "$@" 