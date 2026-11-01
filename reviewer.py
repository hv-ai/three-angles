"""Temporary reviewer access; credentials remain on the server."""
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import sqlite3
import threading
from research import ResearchError

class ReviewerAccess:
    def __init__(self,path,environ=None):
        env=os.environ if environ is None else environ
        self.code=env.get('REVIEW_ACCESS_CODE','')
        self.config={'provider':'nebius','model':env.get('REVIEW_MODEL','Qwen/Qwen3-30B-A3B-Instruct-2507'),
                     'model_key':env.get('NEBIUS_API_KEY',''),'tavily_key':env.get('TAVILY_API_KEY',''),'consent':True}
        self.limit=int(env.get('REVIEW_ACTION_UNITS','30'))
        self.expires=env.get('REVIEW_EXPIRES','2026-11-22T00:00:00+00:00')
        self.enabled=bool(len(self.code)>=12 and self.config['model_key'] and self.config['tavily_key'])
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True);self.lock=threading.Lock()
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS grants (session TEXT PRIMARY KEY)')
            db.execute('CREATE TABLE IF NOT EXISTS usage (units INTEGER NOT NULL)')
            if not db.execute('SELECT 1 FROM usage').fetchone():db.execute('INSERT INTO usage VALUES (0)')
    def available(self):
        try:return self.enabled and datetime.now(timezone.utc)<datetime.fromisoformat(self.expires).astimezone(timezone.utc)
        except ValueError:return False
    def authorize(self,session,code,consent):
        if not self.available():raise ResearchError('Reviewer access is unavailable or has ended.')
        if not consent or not isinstance(code,str) or not secrets.compare_digest(code,self.code):
            raise ResearchError('Enter the reviewer access code and allow live research.')
        with self.lock,closing(sqlite3.connect(self.path)) as db,db:
            db.execute('INSERT OR IGNORE INTO grants VALUES (?)',(session,))
    def run(self,session,units,action):
        if not self.available():raise ResearchError('Reviewer access is unavailable or has ended.')
        with self.lock,closing(sqlite3.connect(self.path)) as db,db:
            if not db.execute('SELECT 1 FROM grants WHERE session=?',(session,)).fetchone():
                raise ResearchError('Connect using the reviewer access code first.')
            used=db.execute('SELECT units FROM usage').fetchone()[0]
            if used+units>self.limit:raise ResearchError('The shared reviewer research allowance is used up. Saved findings and the worked example remain available.')
            # Reserve before starting work; failed attempts still count to bound spending.
            db.execute('UPDATE usage SET units=units+?',(units,))
        return action(dict(self.config))
