from flask import Flask, jsonify, render_template, redirect, url_for, request
from flask_cors import CORS
from services.cache_service import CacheService
import threading
from auth import auth_bp, init_db, ADMIN_SECRET_KEY
from auth import token_required
import jwt
from config import UPDATE_INTERVAL

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_super_segura_aqui'
app.config['DATABASE'] = 'database.db'
CORS(app)
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
    """Página de administração de usuários"""
    return render_template('admin.html')

@app.route('/api/config')
def api_config():
    """Endpoint para retornar configurações do sistema"""
    return jsonify({
        'update_interval': UPDATE_INTERVAL,
        'update_interval_ms': UPDATE_INTERVAL * 1000  # Para JavaScript
    })

@app.route('/login')
def login_page():
    # REMOVER: A verificação automática de token pode causar loops
    # Apenas retornar a página de login diretamente
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
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        # Inicializa o banco dentro do contexto da aplicação
        init_db()
    
    # Inicia o serviço de cache em background
    cache_service.start_background_updates()
    
    # Configura o serviço de comparação no cache service
    from services.comparison_service import ComparisonService
    cache_service.comparison = ComparisonService()
    
    app.run(debug=True, use_reloader=False, port=5000)