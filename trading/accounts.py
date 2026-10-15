"""SQLite accounts, salted password hashes, expiring sessions, and login throttling."""
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
import sqlite3
from threading import BoundedSemaphore
from .storage import ExperimentStore


_hash_slots=BoundedSemaphore(2)


def password_hash(password,salt):
    # Bound concurrent memory-hard hashes on small hosted instances.
    with _hash_slots:
        return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**15,r=8,p=3,maxmem=64*1024*1024).hex()


class Accounts:
    def __init__(self):
        self.store=ExperimentStore()
        with self.store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS user_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_attempts(key TEXT NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS account_migrations(name TEXT PRIMARY KEY,user_id TEXT NOT NULL);
            ''')

    def throttle(self,key,limit=8):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM auth_attempts WHERE created<?',(time.time()-900,))
            count=db.execute('SELECT count(*) FROM auth_attempts WHERE key=?',(key,)).fetchone()[0]
            if count>=limit:raise ValueError('Too many attempts. Wait 15 minutes and try again.')
            db.execute('INSERT INTO auth_attempts VALUES (?,?)',(key,time.time()))

    def register(self,username,password,invitation=''):
        if not isinstance(username,str):raise ValueError('Enter a username.')
        username=str(username).strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,31}',username):
            raise ValueError('Username must be 3–32 letters, numbers, dots, underscores, or dashes.')
        if not isinstance(password,str) or not 12<=len(password)<=128:
            raise ValueError('Choose a password between 12 and 128 characters.')
        if not re.search(r'[A-Za-z]',password):
            raise ValueError('Password must include at least one letter.')
        if not re.search(r'[^A-Za-z]',password):
            raise ValueError('Password must include a number, space, or symbol.')
        # Validate on the server so browser validation cannot bypass the invitation.
        expected_code = os.getenv('QUANTLAB_INVITATION_CODE', 'quantbacktestlab')
        if not expected_code or not hmac.compare_digest(str(invitation).encode(), expected_code.encode()):
            raise ValueError('A valid invitation code is required to create an account.')
        salt=secrets.token_hex(16);hashed=password_hash(password,salt)
        with self.store.connect() as db:
            if db.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
                raise ValueError('That username is unavailable.')
            identifier=uuid.uuid4().hex
            try:db.execute('INSERT INTO users VALUES (?,?,?,?,?)',(identifier,username,salt,hashed,time.time()))
            except sqlite3.IntegrityError:raise ValueError('That username is unavailable.') from None
        return dict(id=identifier,username=username)

    def login(self,username,password):
        if not isinstance(username,str) or len(username)>32:raise ValueError('Invalid username or password.')
        username=str(username).strip().lower()
        if not isinstance(password,str) or len(password)>128:raise ValueError('Invalid username or password.')
        self.throttle('login:'+username)
        with self.store.connect() as db:row=db.execute('SELECT id,username,salt,password_hash FROM users WHERE username=?',(username,)).fetchone()
        salt=row[2] if row else '00'*16
        valid=hmac.compare_digest(password_hash(password,salt),row[3] if row else '0'*128)
        if not row or not valid:raise ValueError('Invalid username or password.')
        with self.store.connect() as db:db.execute('DELETE FROM auth_attempts WHERE key=?',('login:'+username,))
        return dict(id=row[0],username=row[1])

    def session(self,user):
        token=secrets.token_urlsafe(32)
        with self.store.connect() as db:
            db.execute('DELETE FROM user_sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO user_sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],time.time()+604800))
        return token

    def current(self,token):
        if not token:return None
        with self.store.connect() as db:
            row=db.execute('SELECT u.id,u.username FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return dict(id=row[0],username=row[1]) if row else None

    def logout(self,token):
        with self.store.connect() as db:db.execute('DELETE FROM user_sessions WHERE token_hash=?',(hashlib.sha256((token or '').encode()).hexdigest(),))

    def import_local(self,user):
        if os.getenv('QUANTLAB_PUBLIC')=='1':raise ValueError('Import the old local workspace from the desktop app before hosting.')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            first=db.execute('SELECT id FROM users ORDER BY created LIMIT 1').fetchone()
            if not first or first[0]!=user:raise ValueError('Only the first local account can import the old shared workspace.')
            if db.execute('SELECT 1 FROM account_migrations WHERE name=?',('local',)).fetchone():raise ValueError('The old workspace has already been imported.')
            for table in ('experiments','drafts','paper_sessions'):
                if db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table',table)).fetchone():
                    if table=='drafts':
                        db.execute('INSERT OR IGNORE INTO drafts SELECT ?,payload FROM drafts WHERE owner=?',(user,'local'))
                        db.execute('DELETE FROM drafts WHERE owner=?',('local',))
                    else:db.execute(f'UPDATE {table} SET owner=? WHERE owner=?',(user,'local'))
            db.execute('INSERT INTO account_migrations VALUES (?,?)',('local',user))
