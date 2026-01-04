from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, date
import pytz
from app import db
from app.models import Employee, DailySchedule, ScriptStatus, TaskHistory, User, SystemLog
from app.scheduler import TaskScheduler

main = Blueprint('main', __name__)
scheduler = TaskScheduler()
timezone = pytz.timezone('Europe/Samara')

@main.route('/')
def index():
    """Главная страница"""
    # Получаем всех сотрудников
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.id).all()
    
    # Получаем расписание на сегодня
    today = datetime.now(timezone).date()
    
    schedule_data = []
    for emp in employees:
        schedule = DailySchedule.query.filter_by(
            employee_email=emp.email, 
            date=today
        ).first()
        
        # Получаем количество задач сегодня
        task_count = TaskHistory.query.filter_by(
            employee_email=emp.email
        ).filter(
            db.func.date(TaskHistory.assigned_at) == today
        ).count()
        
        schedule_data.append({
            'id': emp.id,
            'name': emp.name,
            'email': emp.email,
            'working_today': schedule.working_today if schedule else False,
            'start_hour': schedule.start_hour if schedule else 8,
            'end_hour': schedule.end_hour if schedule else 17,
            'available': schedule.available if schedule else True,
            'task_count': task_count
        })
    
    # Статус скрипта
    script_status = ScriptStatus.query.get(1)
    
    # Последние логи
    recent_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
    
    # Системный статус
    system_status = scheduler.check_system()
    
    current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('index.html', 
                         schedule=schedule_data,
                         script_status=script_status,
                         recent_logs=recent_logs,
                         system_status=system_status,
                         current_time=current_time)

@main.route('/api/update_schedule', methods=['POST'])
def update_schedule():
    """Обновить расписание сотрудника"""
    try:
        data = request.json
        email = data.get('email')
        working_today = bool(data.get('working_today', False))
        start_hour = int(data.get('start_hour', 8))
        end_hour = int(data.get('end_hour', 17))
        available = bool(data.get('available', True))
        
        # Валидация
        if not 0 <= start_hour <= 23:
            return jsonify({'success': False, 'error': 'Некорректное время начала'}), 400
        if not 0 <= end_hour <= 23:
            return jsonify({'success': False, 'error': 'Некорректное время окончания'}), 400
        if start_hour >= end_hour:
            return jsonify({'success': False, 'error': 'Время окончания должно быть больше времени начала'}), 400
        
        today = datetime.now(timezone).date()
        
        # Находим или создаем запись
        schedule = DailySchedule.query.filter_by(
            employee_email=email, 
            date=today
        ).first()
        
        if schedule:
            schedule.working_today = working_today
            schedule.start_hour = start_hour
            schedule.end_hour = end_hour
            schedule.available = available
        else:
            schedule = DailySchedule(
                employee_email=email,
                date=today,
                working_today=working_today,
                start_hour=start_hour,
                end_hour=end_hour,
                available=available
            )
            db.session.add(schedule)
        
        db.session.commit()
        
        # Логируем изменение
        log_entry = SystemLog(
            level='info',
            message=f'Обновлено расписание для {email}: работа={working_today}, время={start_hour}-{end_hour}, доступен={available}'
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Расписание обновлено'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route('/api/control_script', methods=['POST'])
def control_script():
    """Управление скриптом"""
    try:
        action = request.json.get('action')
        script_status = ScriptStatus.query.get(1)
        
        if action == 'start':
            script_status.is_running = True
            script_status.manual_mode = False
            message = 'Скрипт запущен'
            
            # Логируем
            log_entry = SystemLog(level='info', message='Скрипт запущен через веб-интерфейс')
            db.session.add(log_entry)
            
        elif action == 'stop':
            script_status.is_running = False
            script_status.manual_mode = True
            message = 'Скрипт остановлен'
            
            # Логируем
            log_entry = SystemLog(level='info', message='Скрипт остановлен через веб-интерфейс')
            db.session.add(log_entry)
            
        else:
            return jsonify({'success': False, 'error': 'Неизвестное действие'}), 400
        
        db.session.commit()
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route('/api/get_status', methods=['GET'])
def get_status():
    """Получить текущий статус"""
    try:
        employees = Employee.query.filter_by(is_active=True).order_by(Employee.id).all()
        today = datetime.now(timezone).date()
        
        schedule_data = []
        for emp in employees:
            schedule = DailySchedule.query.filter_by(
                employee_email=emp.email, 
                date=today
            ).first()
            
            task_count = TaskHistory.query.filter_by(
                employee_email=emp.email
            ).filter(
                db.func.date(TaskHistory.assigned_at) == today
            ).count()
            
            schedule_data.append({
                'name': emp.name,
                'email': emp.email,
                'working_today': schedule.working_today if schedule else False,
                'start_hour': schedule.start_hour if schedule else 8,
                'end_hour': schedule.end_hour if schedule else 17,
                'available': schedule.available if schedule else True,
                'task_count': task_count
            })
        
        script_status = ScriptStatus.query.get(1)
        
        # Последние логи
        recent_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(5).all()
        logs_list = [{'level': log.level, 'message': log.message, 'time': log.created_at.strftime('%H:%M:%S')} 
                    for log in recent_logs]
        
        # Системный статус
        system_status = scheduler.check_system()
        
        current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'success': True,
            'schedule': schedule_data,
            'script_status': {
                'is_running': script_status.is_running,
                'manual_mode': script_status.manual_mode
            },
            'recent_logs': logs_list,
            'system_status': system_status,
            'current_time': current_time
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route('/api/run_distribution', methods=['POST'])
def run_distribution():
    """Ручной запуск распределения задач"""
    try:
        assigned = scheduler.distribute_tasks()
        return jsonify({
            'success': True,
            'message': f'Распределение выполнено. Назначено задач: {assigned}',
            'tasks_assigned': assigned
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route('/api/clear_logs', methods=['POST'])
def clear_logs():
    """Очистка логов"""
    try:
        # Удаляем логи старше 7 дней
        from datetime import datetime, timedelta
        week_ago = datetime.now(timezone) - timedelta(days=7)
        
        deleted = SystemLog.query.filter(SystemLog.created_at < week_ago).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Удалено {deleted} старых логов'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
