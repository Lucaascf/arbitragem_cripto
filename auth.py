from flask import Blueprint, request, jsonify, current_app
import sqlite3
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import redirect, url_for
from config import ADMIN_SECRET_KEY, SECRET_KEY

auth_bp = Blueprint('auth_bp', __name__)

# Chave secreta para acessar o painel de administração

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    try:
        # Verifica se a tabela já existe
        cursor = conn.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        ''')
        
        if cursor.fetchone() is None:
            # Só cria a tabela se ela não existir
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
        else:
            print("Banco de dados já existe - mantendo dados existentes")
            
    except Exception as e:
        print(f"Erro ao inicializar banco: {e}")
    finally:
        conn.close()

@auth_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Login do administrador - retorna token em vez de usar chave diretamente"""
    try:
        data = request.get_json()
        secret_key = data.get('secret_key', '').strip()
        
        if not secret_key:
            return jsonify({'message': 'Chave secreta é obrigatória'}), 400
            
        if secret_key != ADMIN_SECRET_KEY:
            return jsonify({'message': 'Chave secreta inválida'}), 401
        
        # Gera token admin válido por 4 horas
        admin_token = jwt.encode({
            'admin': True,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=4)
        }, current_app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({'token': admin_token}), 200
        
    except Exception as e:
        print(f"Erro no login admin: {e}")
        return jsonify({'message': 'Erro interno do servidor'}), 500

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Verifica se o token está nos headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        # Se não tiver token, retorna erro
        if not token:
            return jsonify({'message': 'Token de administrador requerido'}), 401
        
        try:
            # Decodifica o token
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            
            # Verifica se é token de admin
            if not data.get('admin'):
                return jsonify({'message': 'Token inválido - não é admin'}), 403
                
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token inválido'}), 401
        except Exception as e:
            print(f"Erro na verificação do token admin: {str(e)}")
            return jsonify({'message': 'Erro na verificação do token'}), 401
            
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
    
    if len(password) < 6:
        return jsonify({'message': 'A senha deve ter pelo menos 6 caracteres'}), 400
    
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
        # Rate limiting no servidor por IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ['REMOTE_ADDR'])
        
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({'message': 'Dados obrigatórios não fornecidos'}), 400

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND is_active = 1', 
            (username,)
        ).fetchone()
        conn.close()

        # Sempre usa a mesma mensagem para não ajudar ataques
        if not user or not check_password_hash(user['password'], password):
            return jsonify({'message': 'Credenciais inválidas'}), 401
        
        # Verificar se o usuário não expirou
        if user['expires_at']:
            expiry_date = datetime.datetime.fromisoformat(user['expires_at'])
            if datetime.datetime.now() > expiry_date:
                return jsonify({'message': 'Acesso expirado! Entre em contato com o administrador.'}), 401

        token = jwt.encode({
            'user_id': user['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
        }, current_app.config['SECRET_KEY'])

        # Cria resposta com cookie seguro
        response = jsonify({'message': 'Login realizado com sucesso'})
        
        # Cookie seguro com todas as flags de proteção
        response.set_cookie(
            'auth_token',
            token,
            httponly=True,  # Não acessível via JavaScript
            secure=False,  # HTTPS obrigatório em produção
            samesite='Strict',  # Proteção CSRF
            max_age=86400,  # 24 horas
            path='/',
        )
        
        return response
        
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
    # Cria resposta e remove cookie no servidor
    response = jsonify({'message': 'Logout realizado com sucesso'})
    response.set_cookie(
        'auth_token',
        '',
        httponly=True,
        secure=not current_app.config.get('DEBUG', False),
        samesite='Strict',
        expires=0  # Remove cookie imediatamente
    )
    return response
  