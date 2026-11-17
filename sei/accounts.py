"""Contas locais, senhas derivadas e sessões de 24 horas."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager


class Accounts:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
                    salt TEXT NOT NULL, password TEXT NOT NULL, failures INTEGER DEFAULT 0,
                    locked_until REAL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'accounts.db', timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def derive(password, salt):
        return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()

    def register(self, name, email, password):
        name, email = name.strip(), email.strip().casefold()
        if not name or len(name) > 100 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
            raise ValueError('Informe seu nome e um email válido.')
        if not 8 <= len(password) <= 128:
            raise ValueError('Use uma senha com 8 a 128 caracteres.')
        uid, salt = secrets.token_hex(16), secrets.token_hex(16)
        digest = self.derive(password, salt)
        try:
            with self.connect() as db:
                db.execute('INSERT INTO users(id,name,email,salt,password) VALUES (?,?,?,?,?)',
                           (uid, name, email, salt, digest))
        except sqlite3.IntegrityError:
            raise ValueError('Não foi possível criar a conta com esse email. Tente entrar.') from None
        return uid

    def login(self, email, password):
        with self.connect() as db:
            user = db.execute('SELECT * FROM users WHERE email=?', (email.strip().casefold(),)).fetchone()
            salt = user['salt'] if user else '00' * 16
            digest = self.derive(password[:129], salt)
            if not user or user['locked_until'] > time.time() or not hmac.compare_digest(digest, user['password']):
                if user:
                    failures = user['failures'] + 1
                    db.execute('UPDATE users SET failures=?,locked_until=? WHERE id=?',
                               (failures, time.time() + 300 if failures >= 5 else 0, user['id']))
                raise ValueError('Email ou senha incorretos. Após várias tentativas, aguarde 5 minutos.')
            db.execute('UPDATE users SET failures=0,locked_until=0 WHERE id=?', (user['id'],))
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), user['id'], time.time() + 86400))
        return token

    def user(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute('SELECT u.id,u.name,u.email FROM users u JOIN sessions s ON u.id=s.user_id '
                             'WHERE s.token_hash=? AND s.expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        return dict(row) if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def workspace_path(self, uid):
        if not re.fullmatch('[a-f0-9]{32}', uid):
            raise ValueError('Conta inválida.')
        return self.root / 'usuarios' / uid / 'sei.db'
