from concurrent.futures import ThreadPoolExecutor
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import io
from research import Store, Engine, Client, ResearchError, new_case, check_report, validate_decision, public_url, ROLES, TOOLS
from sample import worked_example, BRIEF
from server import handler_for, ThreadingHTTPServer

def call(name,args):return {'choices':[{'message':{'tool_calls':[{'id':'call-test','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}],'usage':{'total_tokens':20}}

class FakeClient:
    barrier=None
    def __init__(self,config=None):pass
    def search(self,query):
        if self.barrier:self.barrier.wait(timeout=4)
        return {'results':[{'url':'https://example.com/evidence','title':'Test evidence','raw_content':'Teams record decisions in a document. This test does not establish willingness to pay.'}]}
    def extract(self,url):return {'results':[{'raw_content':'Teams record decisions in a document.'}]}
    def model(self,messages,tools=None):
        if not tools:
            reports=json.loads(messages[1]['content'])['reports'];ids=[r['findings'][0]['id'] for r in reports.values()]
            return {'choices':[{'message':{'content':json.dumps({'recommendation':'insufficient_evidence','summary':'The test evidence establishes only a documented workflow.','tensions':[{'type':'unanswered','question':'Will users adopt it?','explanation':'This remains untested.','finding_ids':ids}],'next_experiment':'Observe five users completing the same retrieval task.'})}}]}
        outputs=[m for m in messages if m['role']=='tool']
        if len(outputs)==0:return call('search_web',{'query':'documented team decision workflow'})
        if len(outputs)==1:
            first=json.loads(outputs[-1]['content'])['results'][0];return call('open_source',{'source_id':first['id']})
        source=json.loads(outputs[-1]['content'])
        return call('publish_findings',{'conclusion':'A workflow exists; demand remains unknown.','findings':[{'title':'A documented workaround','detail':'The test source describes a document-based method.','kind':'observed','source_id':source['id'],'quote':'Teams record decisions in a document.'}],'unknowns':['Would users switch?'],'next_test':'Observe an actual user retrieving a decision.'})

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'test.sqlite3');self.engines=[]
    def tearDown(self):
        for engine in self.engines:engine.jobs.shutdown(wait=True)
        self.temp.cleanup()
    def engine(self,factory=FakeClient):
        e=Engine(self.store,factory);self.engines.append(e);return e
    def wait(self,e,case_id):
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            with e.lock:active=case_id in e.active
            if not active:return self.store.get(case_id)
            time.sleep(.01)
        self.fail('Research job did not finish in bounded test time.')
    def test_three_actual_workers_research_independently(self):
        class ConcurrentClient(FakeClient):barrier=threading.Barrier(3)
        e=self.engine(ConcurrentClient);case=e.start(BRIEF,{})
        final=self.wait(e,case['id'])
        self.assertEqual(final['status'],'ready');self.assertEqual(len(final['agents']),3)
        for role,agent in final['agents'].items():
            self.assertEqual(agent['status'],'done');self.assertEqual(agent['search_calls'],1)
            self.assertEqual(agent['model_calls'],3);self.assertTrue(agent['report']['findings'][0]['id'].startswith(role))
        self.assertEqual(final['decision']['recommendation'],'insufficient_evidence')
        self.assertEqual(len({e['role'] for e in final['events'] if e['action']=='search'}),3)
    def test_followup_reruns_only_target_and_preserves_history(self):
        e=self.engine();c=e.start(BRIEF,{});before=self.wait(e,c['id'])
        e.followup(c['id'],'skeptic','Find a counterexample to the adoption claim.',{})
        after=self.wait(e,c['id'])
        self.assertEqual(after['agents']['skeptic']['version'],2)
        self.assertEqual(after['agents']['problem']['report'],before['agents']['problem']['report'])
        self.assertEqual(len(after['agents']['skeptic']['history']),1)
        self.assertTrue(set(before['agents']['skeptic']['sources'])<=set(after['agents']['skeptic']['sources']))
        self.assertEqual(len(after['decision_history']),1)
        self.assertEqual(after['decision']['basis']['skeptic'],2)
    def test_fake_native_tool_loops_are_bounded(self):
        class Looper(FakeClient):
            def model(self,messages,tools=None):return call('search_web',{'query':'same query repeated'})
        e=self.engine(Looper);c=e.start(BRIEF,{});final=self.wait(e,c['id'])
        self.assertEqual(final['status'],'partial');self.assertIsNone(final['decision'])
        for a in final['agents'].values():self.assertEqual(a['model_calls'],7);self.assertEqual(a['search_calls'],1)
    def test_source_outage_preserves_partial_reports_without_verdict(self):
        class Outage(FakeClient):
            def search(self,q):raise ResearchError('Controlled search outage')
        e=self.engine(Outage);c=e.start(BRIEF,{});final=self.wait(e,c['id'])
        self.assertEqual(final['status'],'partial');self.assertIsNone(final['decision'])
        self.assertTrue(any(x['action']=='tool_error' for x in final['events']))
    def test_restart_preserves_evidence_marks_interrupted(self):
        c=new_case(BRIEF);c['agents']['problem']['sources']={'x':{'text':'retained'}};self.store.put(c)
        self.store.recover_interrupted();after=self.store.get(c['id'])
        self.assertEqual(after['status'],'interrupted');self.assertEqual(after['agents']['problem']['status'],'interrupted')
        self.assertEqual(after['agents']['problem']['sources']['x']['text'],'retained')
    def test_credential_never_persisted(self):
        e=self.engine();c=e.start(BRIEF,{'model_key':'PRIVATE_MODEL_TEST','tavily_key':'PRIVATE_SEARCH_TEST'})
        final=self.wait(e,c['id']);raw=json.dumps(final)
        self.assertNotIn('PRIVATE_MODEL_TEST',raw);self.assertNotIn('PRIVATE_SEARCH_TEST',raw)
        self.assertNotIn(b'PRIVATE_MODEL_TEST',Path(self.store.path).read_bytes())
    def test_cancellation_blocks_new_provider_work(self):
        c=new_case(BRIEF);self.store.put(c);e=self.engine();e.cancel(c['id'])
        with self.assertRaises(ResearchError):e.assert_active(c['id'])
        self.assertEqual(self.store.get(c['id'])['status'],'cancelled')
    def test_atomic_event_writes_under_concurrency(self):
        c=new_case(BRIEF);self.store.put(c)
        with ThreadPoolExecutor(max_workers=3) as p:list(p.map(lambda i:self.store.event(c['id'],'test','event',str(i)),range(30)))
        events=self.store.get(c['id'])['events'];self.assertEqual(len(events),30)
        self.assertEqual([e['seq'] for e in events],list(range(1,31)))
    def test_observed_finding_cannot_invent_quote_or_source(self):
        report={'conclusion':'x','findings':[{'title':'x','detail':'x','kind':'observed','source_id':'S1','quote':'invented quote'}],'unknowns':[],'next_test':'x'}
        with self.assertRaises(ResearchError):check_report(report,{'S1':{'text':'Actual evidence.'}},{'S1'},'problem',1)
        report['findings'][0]['quote']='Actual evidence.'
        with self.assertRaises(ResearchError):check_report(report,{'S1':{'text':'Actual evidence.'}},set(),'problem',1)
    def test_labeled_inference_can_be_uncited(self):
        report={'conclusion':'x','findings':[{'title':'Hypothesis','detail':'Needs testing.','kind':'inference','source_id':'','quote':''}],'unknowns':['Unproven demand'],'next_test':'Ask users.'}
        actual=check_report(report,{},set(),'skeptic',2);self.assertEqual(actual['findings'][0]['kind'],'inference');self.assertFalse(actual['findings'][0]['quote_checked'])
    def test_synthesis_cannot_reference_unknown_finding(self):
        c=worked_example();data=copy.deepcopy(c['decision']);data['tensions'][0]['finding_ids']=['made-up']
        with self.assertRaises(ResearchError):validate_decision(data,c)
    def test_no_disagreement_is_a_valid_result(self):
        c=worked_example();data=copy.deepcopy(c['decision']);data['tensions']=[]
        self.assertEqual(validate_decision(data,c)['tensions'],[])
    def test_sample_is_explicit_and_its_quotes_match(self):
        c=worked_example();self.assertEqual(c['mode'],'sample')
        for role,a in c['agents'].items():
            self.assertEqual(a['search_calls'],0);self.assertEqual(a['model_calls'],0)
            check_report(a['report'],a['sources'],set(a['sources']),role,1)
    def test_sample_cannot_silently_become_live_followup(self):
        e=self.engine();c=worked_example();self.store.put(c)
        with self.assertRaises(ResearchError):e.followup(c['id'],'problem','Research this again',{})
    def test_public_url_policy(self):
        for url in ['http://127.0.0.1/a','http://localhost/a','file:///etc/passwd','https://user:pass@example.com','https://example.local/path']:
            self.assertFalse(public_url(url))
        self.assertTrue(public_url('https://example.com/source'))
    def test_service_retries_transient_failure_once(self):
        cfg={'provider':'fireworks','model':'test','model_key':'test','tavily_key':'test','consent':True};client=Client(cfg)
        response=io.BytesIO(b'{"results":[]}')
        with patch('research.urllib.request.urlopen',side_effect=[urllib.error.HTTPError('https://api.tavily.com',503,'unavailable',{},None),response]) as mock,patch('research.time.sleep'):
            self.assertEqual(client.search('test')['results'],[]);self.assertEqual(mock.call_count,2)
    def test_real_model_adapter_sends_native_tool_contract(self):
        cfg={'provider':'nebius','model':'test-model','model_key':'test-model-key','tavily_key':'test-search-key','consent':True}
        client=Client(cfg);response=io.BytesIO(json.dumps(call('search_web',{'query':'test'})).encode())
        with patch('research.urllib.request.urlopen',return_value=response) as mock:
            result=client.model([{'role':'user','content':'test brief'}],TOOLS)
        request=mock.call_args.args[0];payload=json.loads(request.data)
        self.assertEqual(request.full_url,'https://api.tokenfactory.nebius.com/v1/chat/completions')
        self.assertEqual(payload['tool_choice'],'required');self.assertEqual(len(payload['tools']),3)
        self.assertEqual(result['choices'][0]['message']['tool_calls'][0]['function']['name'],'search_web')
    def test_auth_failure_is_not_retried_or_leaked(self):
        cfg={'provider':'fireworks','model':'test','model_key':'DO_NOT_LEAK_KEY','tavily_key':'test','consent':True};client=Client(cfg)
        with patch('research.urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://api.fireworks.ai',401,'unauthorized',{},None)) as mock:
            with self.assertRaises(ResearchError) as err:client.model([{'role':'user','content':'test'}],TOOLS)
        self.assertEqual(mock.call_count,1);self.assertNotIn(cfg['model_key'],str(err.exception))
    def test_provider_null_usage_does_not_break_research(self):
        class NullUsage(FakeClient):
            def model(self,messages,tools=None):
                result=super().model(messages,tools);result['usage']=None;return result
        e=self.engine(NullUsage);c=e.start(BRIEF,{})
        self.assertEqual(self.wait(e,c['id'])['status'],'ready')
    def test_cancel_during_synthesis_stays_cancelled(self):
        store=self.store
        class CancelDuringSynthesis(FakeClient):
            def model(self,messages,tools=None):
                result=super().model(messages,tools)
                if tools is None:
                    case_id=store.list()[0]['id']
                    store.update(case_id,lambda c:c.update(cancelled=True,status='cancelled'))
                return result
        e=self.engine(CancelDuringSynthesis);c=e.start(BRIEF,{})
        final=self.wait(e,c['id']);self.assertEqual(final['status'],'cancelled');self.assertIsNone(final['decision'])
    def test_unknown_tool_is_rejected_without_execution(self):
        class UnknownTool(FakeClient):
            def model(self,messages,tools=None):return call('send_email',{'to':'attacker@example.com'})
        e=self.engine(UnknownTool);c=e.start(BRIEF,{})
        final=self.wait(e,c['id'])
        self.assertEqual(final['status'],'partial')
        self.assertTrue(any(x['action']=='tool_error' and 'unavailable' in x['detail'] for x in final['events']))
        self.assertTrue(all(a['search_calls']==0 for a in final['agents'].values()))
    def test_prompt_injection_boundary_reaches_both_model_stages(self):
        seen=[]
        class InspectPrompts(FakeClient):
            def model(self,messages,tools=None):
                seen.append((bool(tools),messages[0]['content']))
                return super().model(messages,tools)
        e=self.engine(InspectPrompts);c=e.start(BRIEF,{})
        self.assertEqual(self.wait(e,c['id'])['status'],'ready')
        self.assertTrue(all('untrusted data' in prompt for _,prompt in seen))
        self.assertTrue(any(not tools for tools,_ in seen))
    def test_retry_synthesis_keeps_completed_research_unchanged(self):
        e=self.engine();c=e.start(BRIEF,{});before=self.wait(e,c['id'])
        self.store.update(c['id'],lambda c:c.update(status='partial',decision=None))
        e.retry_synthesis(c['id'],{});after=self.wait(e,c['id'])
        self.assertEqual(after['status'],'ready');self.assertEqual(after['agents'],before['agents'])
        self.assertIsNotNone(after['decision'])

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'test.sqlite3');self.engine=Engine(self.store,FakeClient)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(self.store,self.engine));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.engine.jobs.shutdown(wait=True);self.temp.cleanup()
    def request(self,path,body=None,origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3);headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
        r=conn.getresponse();status=r.status;raw=r.read();conn.close();return status,raw
    def test_app_and_assets_serve(self):
        for path in ['/','/src/app.js','/src/style.css','/health']:self.assertEqual(self.request(path)[0],200)
        for path in ['/.data/investigations.sqlite3','/research.py','/../server.py']:self.assertEqual(self.request(path)[0],404)
    def test_sample_and_human_decision(self):
        status,raw=self.request('/api/sample',{});self.assertEqual(status,201);c=json.loads(raw)
        status,_=self.request('/api/cases/'+c['id']+'/decision',{'choice':'reshape','note':'Test the narrower audience.'});self.assertEqual(status,200)
        stored=json.loads(self.request('/api/cases/'+c['id'])[1]);self.assertEqual(stored['human_decision']['choice'],'reshape')
    def test_cross_origin_and_bad_brief_rejected(self):
        self.assertEqual(self.request('/api/sample',{},origin='https://unrelated.example')[0],403)
        self.assertEqual(self.request('/api/cases',{'brief':'too short','connection':{}})[0],400)

if __name__=='__main__':unittest.main()
