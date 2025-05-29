from flask import Blueprint, request, jsonify, current_app
import sqlite3
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import redirect, url_for

auth_bp = Blueprint('auth_bp', __name__)

# Chave secreta para acessar o painel de administração
ADMIN_SECRET_KEY = "MT_CRYPTO_ADMIN_2025"

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    try:
        # Remove a tabela antiga se existir
        conn.execute('DROP TABLE IF EXISTS users')
        
        # Cria a nova tabela com a estrutura correta
        conn.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("Banco de dados inicializado com sucesso!")
        
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
    finally:
        conn.close()

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret_key = request.headers.get('X-Admin-Secret') or request.form.get('admin_secret')
        
        if secret_key != ADMIN_SECRET_KEY:
            return jsonify({'message': 'Acesso negado - Chave secreta inválida'}), 403
            
        return f(*args, **kwargs)
    return decorated

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Verificar se o token está nos cookies
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
            return redirect('/login')  # CORREÇÃO: usar URL direta em vez de url_for
        
        try:
            # Decodificar o token
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            conn = get_db_connection()
            current_user = conn.execute(
                'SELECT * FROM users WHERE id = ? AND is_active = 1', 
                (data['user_id'],)
            ).fetchone()
            conn.close()
            
            if not current_user:
                return redirect('/login')  # CORREÇÃO: usar URL direta
            
            # Verificar se o usuário não expirou
            if current_user['expires_at']:
                expiry_date = datetime.datetime.fromisoformat(current_user['expires_at'])
                if datetime.datetime.now() > expiry_date:
                    return redirect('/login')  # CORREÇÃO: usar URL direta
                
        except Exception as e:
            print(f"Erro na verificação do token: {str(e)}")
            return redirect('/login')  # CORREÇÃO: usar URL direta
            
        return f(current_user, *args, **kwargs)
    return decorated

# ROTAS DE ADMINISTRAÇÃO
@auth_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    """Lista todos os usuários"""
    conn = get_db_connection()
    users = conn.execute('''
        SELECT id, username, is_active, expires_at, created_at, updated_at 
        FROM users ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    
    users_list = []
    for user in users:
        user_dict = dict(user)
        # Verificar se expirou
        if user_dict['expires_at']:
            expiry_date = datetime.datetime.fromisoformat(user_dict['expires_at'])
            user_dict['is_expired'] = datetime.datetime.now() > expiry_date
        else:
            user_dict['is_expired'] = False
        users_list.append(user_dict)
    
    return jsonify({'users': users_list})

@auth_bp.route('/api/admin/users', methods=['POST'])
@admin_required
def create_user():
    """Criar novo usuário"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    expires_days = data.get('expires_days')
    
    # Validações
    if not username or not password:
        return jsonify({'message': 'Username e senha são obrigatórios'}), 400
    
    if len(password) != 6 or not password.isdigit():
        return jsonify({'message': 'A senha deve ter exatamente 6 dígitos'}), 400
    
    # Calcular data de expiração
    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = (datetime.datetime.now() + datetime.timedelta(days=expires_days)).isoformat()
    
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO users (username, password, expires_at) 
            VALUES (?, ?, ?)
        ''', (username, hashed_password, expires_at))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Usuário criado com sucesso!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Username já existe!'}), 400

@auth_bp.route('/api/admin/users/<int:user_id>/toggle', methods=['PUT'])
@admin_required
def toggle_user_status(user_id):
    """Ativar/desativar usuário"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({'message': 'Usuário não encontrado'}), 404
    
    new_status = 0 if user['is_active'] else 1
    conn.execute('''
        UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (new_status, user_id))
    conn.commit()
    conn.close()
    
    status_text = 'ativado' if new_status else 'desativado'
    return jsonify({'message': f'Usuário {status_text} com sucesso!'})

@auth_bp.route('/api/admin/users/<int:user_id>/extend', methods=['PUT'])
@admin_required
def extend_user_expiry(user_id):
    """Estender prazo de expiração do usuário"""
    data = request.get_json()
    days = data.get('days', 30)
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({'message': 'Usuário não encontrado'}), 404
    
    # Nova data de expiração
    new_expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
    
    conn.execute('''
        UPDATE users SET expires_at = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (new_expiry, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': f'Prazo estendido por {days} dias!'})

@auth_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Deletar usuário"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        return jsonify({'message': 'Usuário não encontrado'}), 404
    
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Usuário deletado com sucesso!'})

# ROTAS DE AUTENTICAÇÃO
@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({'message': 'Username e senha são obrigatórios!'}), 400

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND is_active = 1', 
            (username,)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user['password'], password):
            return jsonify({'message': 'Credenciais inválidas!'}), 401
        
        # Verificar se o usuário não expirou
        if user['expires_at']:
            expiry_date = datetime.datetime.fromisoformat(user['expires_at'])
            if datetime.datetime.now() > expiry_date:
                return jsonify({'message': 'Acesso expirado! Entre em contato com o administrador.'}), 401

        token = jwt.encode({
            'user_id': user['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
        }, current_app.config['SECRET_KEY'])

        return jsonify({'token': token})
    except Exception as e:
        print(f"Erro no login: {e}")
        return jsonify({'message': 'Erro interno do servidor'}), 500

@auth_bp.route('/api/auth/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    return jsonify({
        'message': 'Token válido',
        'user': {
            'id': current_user['id'],
            'username': current_user['username']
        }
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logout realizado com sucesso'}), 200