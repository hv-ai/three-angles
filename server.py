"""Local server: three concurrent investigators, SQLite history, no third-party packages."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import threading
import os
import secrets
import re
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from research import Store, Engine, ResearchError, ROLES, now
from sample import worked_example
from reviewer import ReviewerAccess

ROOT=Path(__file__).resolve().parent

class VisitorWorkspaces:
    """Separate anonymous browser workspaces for hosted deployments."""
    def __init__(self,path):
        self.path=Path(path);self.backends={};self.lock=threading.Lock()
    def get(self,session):
        with self.lock:
            if session not in self.backends:
                store=Store(self.path/(session+'.sqlite3'));store.recover_interrupted()
                self.backends[session]=(store,Engine(store))
            return self.backends[session]
    def close(self):
        for _,engine in self.backends.values():engine.jobs.shutdown(wait=False,cancel_futures=True)

def handler_for(store,engine,workspaces=None,reviewer=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def backend(self):
            if workspaces is None:return store,engine
            cookie=SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except Exception:pass
            session=cookie.get('three_angles_session')
            session=session.value if session else ''
            if not re.fullmatch(r'[a-f0-9]{64}',session):
                session=secrets.token_hex(32)
                self.session_cookie=f'three_angles_session={session}; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=2592000'
            self.visitor_session=session
            return workspaces.get(session)
        def research_action(self,body,units,action):
            if body.get('connection',{}).get('reviewer'):
                if reviewer is None or not getattr(self,'visitor_session',None):raise ResearchError('Reviewer access is not enabled.')
                if not body.get('connection',{}).get('consent'):raise ResearchError('Allow the brief to be sent for live research.')
                return reviewer.run(self.visitor_session,units,action)
            return action(body.get('connection',{}))
        def reply(self,value,status=200,mime='application/json'):
            raw=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
            if getattr(self,'session_cookie',None):self.send_header('Set-Cookie',self.session_cookie)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            store,engine=self.backend() if urlsplit(self.path).path.startswith('/api/') else (None,None)
            path=urlsplit(self.path).path
            try:
                if path=='/':self.reply((ROOT/'src/index.html').read_bytes(),mime='text/html; charset=utf-8')
                elif path in {'/src/app.js','/src/style.css'}:
                    self.reply((ROOT/path.lstrip('/')).read_bytes(),mime='text/javascript' if path.endswith('.js') else 'text/css')
                elif path=='/api/reviewer':self.reply({'enabled':bool(reviewer and reviewer.available())})
                elif path=='/api/cases':self.reply({'cases':store.list()})
                elif path.startswith('/api/cases/'):
                    case=store.get(path.split('/')[3]);self.reply(case)
                elif path=='/health':self.reply({'ok':True,'roles':list(ROLES)})
                else:self.reply({'error':'Not found'},404)
            except ResearchError as e:self.reply({'error':str(e)},404)
        def do_POST(self):
            origin=self.headers.get('Origin')
            if origin and origin not in {'http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')}:
                self.reply({'error':'Cross-origin request rejected.'},403);return
            store,engine=self.backend()
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=50000:self.reply({'error':'Request is too large or empty.'},413);return
                body=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
                if not isinstance(body,dict):raise ResearchError('Expected a JSON object.')
                if path=='/api/reviewer/connect':
                    if reviewer is None or not getattr(self,'visitor_session',None):raise ResearchError('Reviewer access is not enabled.')
                    reviewer.authorize(self.visitor_session,body.get('code'),body.get('consent'));self.reply({'ok':True})
                elif path=='/api/cases':
                    self.reply(self.research_action(body,3,lambda config:engine.start(body.get('brief'),config)),201)
                elif path=='/api/sample':
                    case=worked_example();store.put(case);self.reply(case,201)
                elif path.startswith('/api/cases/'):
                    parts=path.strip('/').split('/');case_id=parts[2];action=parts[3] if len(parts)>3 else ''
                    if action=='followup':
                        self.research_action(body,1,lambda config:engine.followup(case_id,body.get('role'),body.get('instruction'),config));self.reply({'ok':True})
                    elif action=='cancel':engine.cancel(case_id);self.reply({'ok':True})
                    elif action=='retry-synthesis':
                        self.research_action(body,1,lambda config:engine.retry_synthesis(case_id,config));self.reply({'ok':True})
                    elif action=='decision':
                        choice=body.get('choice');note=body.get('note','')
                        if choice not in {'pursue','reshape','drop','more_research'} or not isinstance(note,str) or len(note)>1200:raise ResearchError('Choose a decision and a short rationale.')
                        def decide(c):
                            if c['status'] not in {'ready','partial'}:raise ResearchError('Wait for the investigation to finish before recording your decision.')
                            c['human_decision']={'choice':choice,'note':note,'time':now(),'basis':{r:a['version'] for r,a in c['agents'].items()}}
                        store.update(case_id,decide);store.event(case_id,'human','decision',choice,reason=note);self.reply({'ok':True})
                    else:self.reply({'error':'Not found'},404)
                else:self.reply({'error':'Not found'},404)
            except (ResearchError,ValueError,KeyError,TypeError) as e:
                message=str(e) if isinstance(e,ResearchError) else 'Malformed request.'
                self.reply({'error':message},400)
    return Handler

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host',default=os.environ.get('HOST','127.0.0.1'));parser.add_argument('--port',type=int,default=int(os.environ.get('PORT',8766)))
    args,_=parser.parse_known_args()
    data=Path(os.environ.get('DATA_DIR',str(ROOT/'.data')))
    store=Store(data/'investigations.sqlite3');engine=Engine(store)
    workspaces=VisitorWorkspaces(data/'visitors') if os.environ.get('HOSTED')=='1' else None
    reviewer=ReviewerAccess(data/'reviewer.sqlite3') if workspaces else None
    try:
        server=ThreadingHTTPServer((args.host,args.port),handler_for(store,engine,workspaces,reviewer))
    except OSError:
        engine.jobs.shutdown(wait=False)
        parser.exit(1,f'Port {args.port} is unavailable. Close the existing Three Angles server or choose --port 8767.\n')
    store.recover_interrupted()
    print(f'Three Angles: http://{args.host}:{args.port}',flush=True)
    print('Python server stays open while investigators work. Ctrl+C stops it.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();engine.jobs.shutdown(wait=False,cancel_futures=True)
        if workspaces:workspaces.close()
