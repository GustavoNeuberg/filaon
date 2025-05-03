import sqlite3

conn = sqlite3.connect('fila.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS fila (
        id TEXT PRIMARY KEY,
        telefone TEXT UNIQUE,
        nome TEXT,
        entrada TEXT
    )
''')
conn.commit()
conn.close()

print("Banco de dados 'fila.db' criado com sucesso!")
