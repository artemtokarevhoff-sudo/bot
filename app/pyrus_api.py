import requests
import logging
from datetime import datetime, timedelta
import pytz
from app import db
from app.models import SystemLog

logger = logging.getLogger(__name__)

class PyrusAPI:
    def __init__(self):
        from config.pyrus_config import PYRUS_CONFIG
        self.config = PYRUS_CONFIG
        
    def _log(self, level, message):
        """Логирование в базу данных"""
        log_entry = SystemLog(level=level, message=message)
        db.session.add(log_entry)
        db.session.commit()
        getattr(logger, level)(message)
    
    def update_access_token(self):
        """Обновление access_token"""
        try:
            data = {
                'login': self.config['LOGIN'],
                'security_key': self.config['SECURITY_KEY']
            }
            
            response = requests.post(
                self.config['AUTH_URL'],
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                access_token = response.json().get("access_token")
                self.config['ACCESS_TOKEN'] = access_token
                self._log('info', f'Access token обновлен')
                return True
            else:
                self._log('error', f'Ошибка обновления токена: {response.status_code}')
                return False
        except Exception as e:
            self._log('error', f'Исключение при обновлении токена: {str(e)}')
            return False
    
    def fetch_tasks(self):
        """Получение задач из Pyrus"""
        url = 'https://api.pyrus.com/v4/forms/607869/register?steps=4'
        headers = {'Authorization': f'Bearer {self.config["ACCESS_TOKEN"]}'}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                tasks = [task['id'] for task in response.json().get('tasks', [])]
                self._log('info', f'Получено {len(tasks)} задач')
                return tasks
            elif response.status_code == 401:
                self._log('warning', 'Требуется обновление токена')
                if self.update_access_token():
                    return self.fetch_tasks()
                else:
                    return []
            else:
                self._log('error', f'Ошибка получения задач: {response.status_code}')
                return []
        except Exception as e:
            self._log('error', f'Исключение при получении задач: {str(e)}')
            return []
    
    def get_task_responsible(self, task_id):
        """Получить ответственного по задаче"""
        url = f'https://api.pyrus.com/v4/tasks/{task_id}'
        headers = {'Authorization': f'Bearer {self.config["ACCESS_TOKEN"]}'}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                task_data = response.json()
                fields = task_data.get('task', {}).get('fields', [])
                
                # Поиск ответственного технолога
                for field in fields:
                    if field.get('name') == 'Ответственный технолог':
                        responsible = field.get('value', {})
                        if isinstance(responsible, dict):
                            return responsible.get('email')
                
                # Альтернативный поиск в подформах
                for field in fields:
                    if field.get('name') == 'Создание запроса Специалистом КС':
                        subfields = field.get('value', {}).get('fields', [])
                        for subfield in subfields:
                            if subfield.get('name') == 'Тип запроса':
                                sub_subfields = subfield.get('value', {}).get('fields', [])
                                for sub_subfield in sub_subfields:
                                    if sub_subfield.get('name') == 'Обработка запроса Технологом':
                                        tech_fields = sub_subfield.get('value', {}).get('fields', [])
                                        for tech_field in tech_fields:
                                            if tech_field.get('name') == 'Ответственный технолог':
                                                responsible = tech_field.get('value', {})
                                                if isinstance(responsible, dict):
                                                    return responsible.get('email')
                return None
            else:
                self._log('error', f'Ошибка получения задачи {task_id}: {response.status_code}')
                return None
        except Exception as e:
            self._log('error', f'Исключение при получении задачи {task_id}: {str(e)}')
            return None
    
    def change_responsible(self, task_id, new_responsible_email):
        """Изменить ответственного по задаче"""
        url = f'https://api.pyrus.com/v4/tasks/{task_id}/comments'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.config["ACCESS_TOKEN"]}'
        }
        
        data = {
            "field_updates": [{
                "id": 106,
                "value": {"email": new_responsible_email}
            }]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                self._log('info', f'Задача {task_id} назначена на {new_responsible_email}')
                return True
            else:
                self._log('error', f'Ошибка назначения задачи {task_id}: {response.status_code}')
                return False
        except Exception as e:
            self._log('error', f'Исключение при назначении задачи {task_id}: {str(e)}')
            return False
