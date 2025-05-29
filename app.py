import os
import logging
from datetime import datetime  # ← ADICIONE ESTA LINHA
from flask import Flask, jsonify, render_template, redirect, request
from flask_cors import CORS
from services.cache_service import CacheService
import threading
from auth import auth_bp, init_db
from auth import token_required
import jwt
from config import UPDATE_INTERVAL, SECRET_KEY, DEBUG, PORT

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY  # Usa a chave do .env
app.config['DATABASE'] = os.getenv('DATABASE_PATH', 'database.db')

# Configuração de CORS
CORS(app)

# Headers de segurança
@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

cache_service = CacheService()

# Registre o blueprint de autenticação
app.register_blueprint(auth_bp)

@app.route('/')
@token_required
def index(current_user):
    return render_template('index.html')

@app.route('/calculadora')
@token_required
def calculadora(current_user):
    return render_template('calculadora.html')

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

@app.route('/api/config')
def api_config():
    return jsonify({
        'update_interval': UPDATE_INTERVAL,
        'update_interval_ms': UPDATE_INTERVAL * 1000
    })

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/api/comparacao')
def api_comparacao():
    try:
        cache = cache_service.get_cache()
        
        if cache['data'] is None:
            cache_service.update_cache()
            cache = cache_service.get_cache()
        
        return jsonify({
            'data': cache['data'],
            'last_update': cache['last_update'].isoformat() if cache['last_update'] else None,
            'total_crossings_24h': sum(c['count'] for c in cache_service.comparison.crossings_24h.values()),
            'total_crossings_30min': sum(c['count'] for c in cache_service.comparison.crossings_30min.values())
        })
    except Exception as e:
        app.logger.error(f'Erro na API de comparação: {str(e)}')
        return jsonify({'error': str(e)}), 500

# Endpoint de health check
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    with app.app_context():
        init_db()
    
    cache_service.start_background_updates()
    
    from services.comparison_service import ComparisonService
    cache_service.comparison = ComparisonService()
    
    app.run(debug=DEBUG, use_reloader=False, port=PORT, host='0.0.0.0' if not DEBUG else '127.0.0.1')