"""Local server: three concurrent investigators, SQLite history, no third-party packages."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import threading
from urllib.parse import urlsplit
from research import Store, Engine, ResearchError, ROLES, now
from sample import worked_example

ROOT=Path(__file__).resolve().parent

def handler_for(store,engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value,status=200,mime='application/json'):
            raw=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            path=urlsplit(self.path).path
            try:
                if path=='/':self.reply((ROOT/'src/index.html').read_bytes(),mime='text/html; charset=utf-8')
                elif path in {'/src/app.js','/src/style.css'}:
                    self.reply((ROOT/path.lstrip('/')).read_bytes(),mime='text/javascript' if path.endswith('.js') else 'text/css')
                elif path=='/api/cases':self.reply({'cases':store.list()})
                elif path.startswith('/api/cases/'):
                    case=store.get(path.split('/')[3]);self.reply(case)
                elif path=='/health':self.reply({'ok':True,'roles':list(ROLES)})
                else:self.reply({'error':'Not found'},404)
            except ResearchError as e:self.reply({'error':str(e)},404)
        def do_POST(self):
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):
                self.reply({'error':'Cross-origin request rejected.'},403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=50000:self.reply({'error':'Request is too large or empty.'},413);return
                body=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
                if not isinstance(body,dict):raise ResearchError('Expected a JSON object.')
                if path=='/api/cases':
                    self.reply(engine.start(body.get('brief'),body.get('connection',{})),201)
                elif path=='/api/sample':
                    case=worked_example();store.put(case);self.reply(case,201)
                elif path.startswith('/api/cases/'):
                    parts=path.strip('/').split('/');case_id=parts[2];action=parts[3] if len(parts)>3 else ''
                    if action=='followup':
                        engine.followup(case_id,body.get('role'),body.get('instruction'),body.get('connection',{}));self.reply({'ok':True})
                    elif action=='cancel':engine.cancel(case_id);self.reply({'ok':True})
                    elif action=='retry-synthesis':
                        engine.retry_synthesis(case_id,body.get('connection',{}));self.reply({'ok':True})
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
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8766)
    args,_=parser.parse_known_args()
    store=Store(ROOT/'.data/investigations.sqlite3');engine=Engine(store)
    try:
        server=ThreadingHTTPServer((args.host,args.port),handler_for(store,engine))
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
