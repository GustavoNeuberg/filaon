import os
import sqlite3
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

# Configuração
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'minha_chave_secreta')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_PATH = 'fila.db'

# Banco de Dados
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS fila (
                id TEXT PRIMARY KEY,
                telefone TEXT UNIQUE NOT NULL,
                nome TEXT NOT NULL,
                entrada TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                telefone TEXT PRIMARY KEY,
                nome TEXT,
                visitas INTEGER,
                ultima_visita TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS historico (
                id TEXT PRIMARY KEY,
                telefone TEXT,
                nome TEXT,
                entrada TEXT,
                saida TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS atendimento (
                id TEXT PRIMARY KEY,
                telefone TEXT,
                nome TEXT,
                inicio TEXT
            )
        ''')
        conn.commit()

init_db()

def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn

def emitir_atualizacao_fila():
    with db_conn() as conn:
        c = conn.cursor()
        c.execute('SELECT id, telefone, nome, entrada FROM fila ORDER BY entrada')
        fila = [{'id': row[0], 'telefone': row[1], 'nome': row[2], 'entrada': row[3]} for row in c.fetchall()]
    socketio.emit('atualizar_fila', fila)

def emitir_cliente_atual():
    with db_conn() as conn:
        c = conn.cursor()
        c.execute('SELECT id, nome FROM atendimento LIMIT 1')
        cliente = c.fetchone()
        if cliente:
            socketio.emit('cliente_atual', {'id': cliente[0], 'nome': cliente[1]})
        else:
            socketio.emit('cliente_atual', {'id': None, 'nome': None})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/entrar-fila', methods=['POST'])
def entrar_fila():
    try:
        data = request.get_json(force=True)
        telefone = data.get('telefone')
        nome = data.get('nome', 'Cliente').strip()

        if not telefone:
            return jsonify({'error': 'Telefone é obrigatório'}), 400

        cliente_id = str(uuid.uuid4())
        entrada = datetime.now().isoformat()

        with db_conn() as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM fila WHERE telefone = ?', (telefone,))
            if c.fetchone():
                return jsonify({'error': 'Você já está na fila!'}), 400

            c.execute('INSERT INTO fila (id, telefone, nome, entrada) VALUES (?, ?, ?, ?)',
                      (cliente_id, telefone, nome, entrada))

            c.execute('SELECT visitas FROM usuarios WHERE telefone = ?', (telefone,))
            user = c.fetchone()
            if user:
                c.execute('UPDATE usuarios SET visitas = visitas + 1, ultima_visita = ? WHERE telefone = ?',
                          (entrada, telefone))
            else:
                c.execute('INSERT INTO usuarios (telefone, nome, visitas, ultima_visita) VALUES (?, ?, ?, ?)',
                          (telefone, nome, 1, entrada))

        emitir_atualizacao_fila()
        app.logger.info(f'{nome} entrou na fila.')
        return jsonify({'message': f'{nome}, você entrou na fila!', 'cliente_id': cliente_id, 'nome': nome})
    except Exception as e:
        app.logger.error(f"Erro /entrar-fila: {e}")
        return jsonify({'error': 'Erro no servidor'}), 500

@app.route('/posicao/<cliente_id>')
def posicao(cliente_id):
    try:
        with db_conn() as conn:
            c = conn.cursor()
            c.execute('SELECT entrada FROM fila WHERE id = ?', (cliente_id,))
            cliente = c.fetchone()
            if not cliente:
                return jsonify({'error': 'Não está na fila'}), 404

            entrada_cliente = cliente[0]
            c.execute('SELECT COUNT(*) FROM fila WHERE entrada <= ?', (entrada_cliente,))
            posicao = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM fila')
            total = c.fetchone()[0]

        return jsonify({'posicao': posicao, 'total': total})
    except Exception as e:
        app.logger.error(f"Erro /posicao/{cliente_id}: {e}")
        return jsonify({'error': 'Erro no servidor'}), 500

@app.route('/proximo', methods=['POST'])
def proximo():
    try:
        with db_conn() as conn:
            c = conn.cursor()
            c.execute('SELECT id, nome, telefone, entrada FROM fila ORDER BY entrada LIMIT 1')
            cliente = c.fetchone()

            if not cliente:
                return jsonify({'error': 'Nenhum cliente na fila'}), 404

            cliente_id, nome, telefone, entrada = cliente
            saida = datetime.now().isoformat()

            c.execute('DELETE FROM fila WHERE id = ?', (cliente_id,))
            c.execute('INSERT INTO historico (id, telefone, nome, entrada, saida) VALUES (?, ?, ?, ?, ?)',
                      (cliente_id, telefone, nome, entrada, saida))

            c.execute('DELETE FROM atendimento')
            c.execute('INSERT INTO atendimento (id, telefone, nome, inicio) VALUES (?, ?, ?, ?)',
                      (cliente_id, telefone, nome, saida))

        socketio.emit('cliente_chamado', {'cliente_id': cliente_id, 'nome': nome})
        emitir_atualizacao_fila()
        emitir_cliente_atual()
        app.logger.info(f'{nome} foi chamado para atendimento.')
        return jsonify({'message': f'{nome} foi chamado para atendimento!', 'nome': nome, 'telefone': telefone})
    except Exception as e:
        app.logger.error(f"Erro /proximo: {e}")
        return jsonify({'error': 'Erro no servidor'}), 500

@app.route('/sair-fila/<cliente_id>', methods=['POST'])
def sair_fila(cliente_id):
    try:
        with db_conn() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM fila WHERE id = ?', (cliente_id,))
        emitir_atualizacao_fila()
        app.logger.info(f'Cliente {cliente_id} saiu da fila.')
        return jsonify({'message': 'Você saiu da fila.'})
    except Exception as e:
        app.logger.error(f"Erro /sair-fila: {e}")
        return jsonify({'error': 'Erro no servidor'}), 500

@app.route('/fila')
def ver_fila():
    try:
        with db_conn() as conn:
            c = conn.cursor()
            c.execute('SELECT id, telefone, nome, entrada FROM fila ORDER BY entrada')
            fila = [{'id': row[0], 'telefone': row[1], 'nome': row[2], 'entrada': row[3]} for row in c.fetchall()]
        return jsonify({'fila': fila})
    except Exception as e:
        app.logger.error(f"Erro /fila: {e}")
        return jsonify({'error': 'Erro no servidor'}), 500

@app.route('/admin')
def admin():
    return render_template('admin.html')

if __name__ == '__main__':
    app.logger.info("Servidor rodando em http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000)
