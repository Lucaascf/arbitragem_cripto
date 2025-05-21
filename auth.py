from flask import Blueprint, request, jsonify, current_app
import sqlite3
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import redirect, url_for

auth_bp = Blueprint('auth_bp', __name__)

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Primeiro, verificar se o token está nos cookies
        if 'auth_token' in request.cookies:
            token = request.cookies.get('auth_token')
        
        # Se não estiver nos cookies, verificar nos headers
        elif 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if ' ' in auth_header:
                token = auth_header.split(" ")[1]
            else:
                token = auth_header
                
        # Se não tiver token, redirecionar para login
        if not token:
            return redirect(url_for('login_page'))
        
        try:
            # Decodificar o token
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            conn = get_db_connection()
            current_user = conn.execute('SELECT * FROM users WHERE id = ?', (data['user_id'],)).fetchone()
            conn.close()
            
            if not current_user:
                return redirect(url_for('login_page'))
                
        except Exception as e:
            # Para debug apenas (remover em produção)
            print(f"Erro na verificação do token: {str(e)}")
            # Se o token for inválido, redirecionar para login
            return redirect(url_for('login_page'))
            
        return f(current_user, *args, **kwargs)
    return decorated

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({'message': 'Dados incompletos!'}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                     (name, email, hashed_password))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Usuário registrado com sucesso!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Email já está em uso!'}), 400
    except Exception as e:
        return jsonify({'message': 'Erro no servidor', 'error': str(e)}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Credenciais faltando!'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user['password'], password):
        return jsonify({'message': 'Credenciais inválidas!'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }, current_app.config['SECRET_KEY'])

    return jsonify({'token': token})

@auth_bp.route('/api/auth/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    return jsonify({
        'message': 'Token válido',
        'user': {
            'id': current_user['id'],
            'name': current_user['name'],
            'email': current_user['email']
        }
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    # Com JWT, o logout é feito no cliente simplesmente removendo o token
    return jsonify({'message': 'Logout realizado com sucesso'}), 200