import logging
import pytz
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import DailySchedule, ScriptStatus, TaskHistory, Employee, SystemLog
from app.pyrus_api import PyrusAPI

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.pyrus_api = PyrusAPI()
        self.timezone = pytz.timezone('Europe/Samara')
    
    def _log(self, level, message):
        """Логирование в базу данных"""
        log_entry = SystemLog(level=level, message=message)
        db.session.add(log_entry)
        db.session.commit()
        getattr(logger, level)(message)
    
    def is_within_work_hours(self, current_hour, start_hour, end_hour):
        """Проверка, находится ли текущее время в рабочих часах"""
        # Вычитаем 10 минут (0.17 часа) до окончания работы
        return start_hour <= current_hour < (end_hour - 0.17)
    
    def get_working_technologists(self):
        """Получить список работающих технологов на текущий момент"""
        current_time = datetime.now(self.timezone)
        current_hour = current_time.hour + current_time.minute / 60.0
        today = current_time.date()
        
        # Получаем расписание на сегодня
        schedules = DailySchedule.query.filter_by(
            date=today,
            working_today=True,
            available=True
        ).all()
        
        working_techs = []
        for schedule in schedules:
            if self.is_within_work_hours(current_hour, schedule.start_hour, schedule.end_hour):
                # Получаем количество задач сегодня
                task_count = TaskHistory.query.filter_by(
                    employee_email=schedule.employee_email
                ).filter(
                    func.date(TaskHistory.assigned_at) == today
                ).count()
                
                if task_count < 20:  # Максимум 20 задач в день
                    working_techs.append({
                        'email': schedule.employee_email,
                        'name': Employee.query.filter_by(email=schedule.employee_email).first().name,
                        'task_count': task_count,
                        'start_hour': schedule.start_hour,
                        'end_hour': schedule.end_hour
                    })
        
        return working_techs
    
    def distribute_tasks(self):
        """Основная функция распределения задач"""
        try:
            # Проверяем статус скрипта
            status = ScriptStatus.query.get(1)
            if not status or not status.is_running:
                self._log('info', 'Скрипт остановлен, пропускаем распределение')
                return 0
            
            current_time = datetime.now(self.timezone)
            current_hour = current_time.hour + current_time.minute / 60.0
            
            # Проверяем рабочее время (8:30 - 20:00)
            if current_hour < 8.5 or current_hour >= 20:
                self._log('info', f'Вне рабочего времени: {current_hour:.2f}')
                return 0
            
            # Получаем работающих технологов
            working_techs = self.get_working_technologists()
            
            if not working_techs:
                self._log('warning', 'Нет доступных технологов для распределения')
                return 0
            
            # Получаем задачи из Pyrus
            tasks = self.pyrus_api.fetch_tasks()
            
            if not tasks:
                self._log('info', 'Нет задач для распределения')
                return 0
            
            # Сортируем технологов по количеству задач (Round Robin)
            working_techs.sort(key=lambda x: x['task_count'])
            
            # Распределяем задачи
            tasks_assigned = 0
            today = current_time.date()
            
            for task_id in tasks:
                # Проверяем, есть ли уже ответственный
                current_responsible = self.pyrus_api.get_task_responsible(task_id)
                
                if current_responsible:
                    # Если задача уже назначена на работающего технолога, пропускаем
                    if any(tech['email'] == current_responsible for tech in working_techs):
                        self._log('info', f'Задача {task_id} уже назначена на {current_responsible}')
                        continue
                
                # Выбираем технолога с наименьшим количеством задач
                selected_tech = working_techs[0]
                
                # Назначаем задачу
                if self.pyrus_api.change_responsible(task_id, selected_tech['email']):
                    # Сохраняем в историю
                    task_history = TaskHistory(
                        task_id=task_id,
                        employee_email=selected_tech['email']
                    )
                    db.session.add(task_history)
                    
                    # Обновляем счетчик задач
                    selected_tech['task_count'] += 1
                    tasks_assigned += 1
                    
                    # Пересортировка для Round Robin
                    working_techs.sort(key=lambda x: x['task_count'])
                    
                    self._log('info', f'Задача {task_id} назначена на {selected_tech["email"]}')
            
            db.session.commit()
            self._log('info', f'Распределение завершено. Назначено задач: {tasks_assigned}')
            return tasks_assigned
            
        except Exception as e:
            self._log('error', f'Критическая ошибка при распределении: {str(e)}')
            db.session.rollback()
            return 0
    
    def check_system(self):
        """Проверка состояния системы"""
        status = ScriptStatus.query.get(1)
        working_techs = self.get_working_technologists()
        current_time = datetime.now(self.timezone)
        
        system_status = {
            'timestamp': current_time.isoformat(),
            'script_running': status.is_running if status else False,
            'working_technologists': len(working_techs),
            'technologists': working_techs,
            'current_hour': current_time.hour + current_time.minute / 60.0,
            'within_work_hours': 8.5 <= (current_time.hour + current_time.minute / 60.0) < 20
        }
        
        return system_status