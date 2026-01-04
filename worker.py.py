import time
import logging
import sys
import os
from datetime import datetime
import pytz

# Настройка путей
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.scheduler import TaskScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def worker_loop():
    """Основной цикл воркера"""
    app = create_app()
    
    with app.app_context():
        scheduler = TaskScheduler()
        
        logger.info("Воркер запущен и готов к работе")
        
        while True:
            try:
                current_time = datetime.now(pytz.timezone('Europe/Samara'))
                current_hour = current_time.hour + current_time.minute / 60.0
                
                # Проверяем, нужно ли запускать распределение
                if 8.5 <= current_hour < 20:
                    logger.info(f"[{current_time.strftime('%H:%M:%S')}] Запуск распределения задач...")
                    
                    # Запускаем распределение
                    tasks_assigned = scheduler.distribute_tasks()
                    
                    if tasks_assigned > 0:
                        logger.info(f"Назначено задач: {tasks_assigned}")
                else:
                    logger.debug(f"[{current_time.strftime('%H:%M:%S')}] Вне рабочего времени ({current_hour:.2f})")
                
                # Ждем 60 секунд
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Воркер остановлен по запросу пользователя")
                break
            except Exception as e:
                logger.error(f"Ошибка в воркере: {e}")
                time.sleep(60)  # Ждем перед повторной попыткой

if __name__ == '__main__':
    worker_loop()