import os
from dotenv import load_dotenv

load_dotenv()

# Попытка импорта из локального файла account.py
try:
    from data.account import login, security_key, access_token
    PYRUS_CONFIG = {
        'LOGIN': login,
        'SECURITY_KEY': security_key,
        'ACCESS_TOKEN': access_token,
        'AUTH_URL': 'https://api.pyrus.com/v4/auth'
    }
except ImportError:
    # Если файла нет, используем переменные окружения
    PYRUS_CONFIG = {
        'LOGIN': os.environ.get('PYRUS_LOGIN', ''),
        'SECURITY_KEY': os.environ.get('PYRUS_SECURITY_KEY', ''),
        'ACCESS_TOKEN': os.environ.get('PYRUS_ACCESS_TOKEN', ''),
        'AUTH_URL': 'https://api.pyrus.com/v4/auth'
    }

# Валидация конфигурации
if not all([PYRUS_CONFIG['LOGIN'], PYRUS_CONFIG['SECURITY_KEY']]):
    print("ВНИМАНИЕ: Конфигурация Pyrus не настроена!")
    print("Создайте файл data/account.py с содержимым:")
    print("""
login = "ваш_логин"
security_key = "ваш_ключ"
access_token = "ваш_токен"
""")
    print("Или установите переменные окружения:")
    print("PYRUS_LOGIN, PYRUS_SECURITY_KEY, PYRUS_ACCESS_TOKEN")