import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    
    # Конфигурация
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    
    # Создание таблиц и начальных данных
    with app.app_context():
        from app.models import Employee, ScriptStatus
        db.create_all()
        
        # Добавляем начальные данные если таблица пустая
        if Employee.query.count() == 0:
            initial_employees = [
                Employee(name='Екатерина Максимова', email='Ekaterina.Maksimova2@hoff.ru'),
                Employee(name='Светлана Филатова', email='Svetlana.Filatova@hoff.ru'),
                Employee(name='Артем Токарев', email='Artem.Tokarev@hoff.ru'),
                Employee(name='Елена Валентова', email='Elena.Valentova@hoff.ru'),
            ]
            db.session.add_all(initial_employees)
            db.session.commit()
            print("Добавлены начальные данные сотрудников")
        
        # Инициализация статуса скрипта
        if ScriptStatus.query.get(1) is None:
            status = ScriptStatus(id=1, is_running=False, manual_mode=False)
            db.session.add(status)
            db.session.commit()
            print("Инициализирован статус скрипта")
    
    # Регистрация blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Обработчики ошибок
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    return app