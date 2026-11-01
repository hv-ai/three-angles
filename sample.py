"""Curated example, explicitly not a live or autonomous investigation."""
from research import new_case, now, validate_decision

BRIEF='An assistant for small remote teams that turns recurring meeting transcripts into a searchable log of decisions, owners and unresolved questions. Is this a useful gap, or does it duplicate existing meeting tools?'

def worked_example():
    c=new_case(BRIEF,'sample');c['status']='ready'
    excerpts={
      'gitlab':{'id':'sample-gitlab','title':'GitLab communication handbook','url':'https://handbook.gitlab.com/handbook/communication/','text':'conclusions of offline conversations are written down.','retrieved_at':'2026-10-25','query':'Curated source snapshot, not a live search'},
      'otter':{'id':'sample-otter','title':'Otter product page','url':'https://otter.ai/','text':'Clear next steps are automatically captured and assigned from every meeting.','retrieved_at':'2026-10-25','query':'Curated source snapshot, not a live search'},
      'fireflies':{'id':'sample-fireflies','title':'Fireflies product page','url':'https://fireflies.ai/','text':'Transcribe, summarize, search, and analyze all your team conversations.','retrieved_at':'2026-10-25','query':'Curated source snapshot, not a live search'}}
    def finding(role,num,title,detail,kind,sid='',quote=''):
        return {'id':f'{role}-v1-F{num}','title':title,'detail':detail,'kind':kind,'source_id':sid,'quote':quote,'quote_checked':bool(sid)}
    reports={
      'problem':{'conclusion':'Documenting meeting conclusions is an established workflow. Demand for a separate paid tool is still untested.',
       'findings':[finding('problem',1,'There is a real documentation workflow','GitLab documents an expectation that conclusions from offline conversations should be recorded. This establishes a workflow example, not a market-size estimate.','observed','sample-gitlab',excerpts['gitlab']['text']),
                   finding('problem',2,'A narrower user might have a sharper problem','A team lead revisiting decisions across several meetings is a possible target. Interviews would need to establish how often this fails today and what the consequence is.','inference')],
       'unknowns':['Who repeatedly loses a decision despite using meeting notes?','Would a searchable log change an actual weekly workflow?'],
       'next_test':'Interview five team leads using their last two meeting records. Ask them to retrieve one decision and its current owner, and observe the workaround.'},
      'solutions':{'conclusion':'Generic meeting capture, search and follow-up already overlap with named products. The proposal needs a more specific job.',
       'findings':[finding('solutions',1,'Action-item capture is already marketed','Otter describes automatic next-step capture and assignment. This is an official product claim, not an independent performance test.','observed','sample-otter',excerpts['otter']['text']),
                   finding('solutions',2,'Search and summaries are already marketed','Fireflies describes conversation transcription, summarization, search and analysis. This is material overlap with the proposed broad feature set.','observed','sample-fireflies',excerpts['fireflies']['text'])],
       'unknowns':['Do these products handle changed or reversed decisions the way the target users need?','What does the target team already pay for?'],
       'next_test':'Run the same three meeting records through the existing tools and a manual decision log. Compare retrieval of the latest decision, owner and unresolved dependency.'},
      'skeptic':{'conclusion':'The important assumption is switching value. A new summary is unlikely to be sufficient evidence of a new product need.',
       'findings':[finding('skeptic',1,'Useful output does not establish adoption','A person can like a demonstration and still continue using their existing notes. The experiment should test a repeated task, not whether a generated summary looks appealing.','inference'),
                   finding('skeptic',2,'The differentiating capability is unproven','Handling a decision that changes across meetings might differentiate the idea, but the current evidence does not establish that users need it or that existing tools fail at it.','unknown')],
       'unknowns':['Will people trust the latest-decision interpretation enough to use it?','Does correcting a wrong owner cost more effort than a manual log?'],
       'next_test':'Give participants a decision that was reversed in a later meeting. Compare time and errors using their current method and the proposed decision log.'}}
    for role,report in reports.items():
        agent=c['agents'][role];agent.update(status='done',version=1,report={**report,'version':1,'created_at':now()})
    c['agents']['problem']['sources']={'sample-gitlab':excerpts['gitlab']}
    c['agents']['solutions']['sources']={s['id']:s for k,s in excerpts.items() if k!='gitlab'}
    c['decision']=validate_decision({'recommendation':'reshape','summary':'Investigate changed decisions across meetings before building another general meeting-summary tool. The public evidence shows a documentation workflow and substantial feature overlap; it does not establish willingness to pay.',
      'tensions':[{'type':'tradeoff','question':'A real workflow, but is there a distinct product gap?','explanation':'The documentation example supports the existence of the task. The competitor capabilities show that a broad summary-and-search pitch overlaps with existing products. Both findings can be true.','finding_ids':['problem-v1-F1','solutions-v1-F1','solutions-v1-F2']},
                  {'type':'unanswered','question':'Would a changed-decision tracker beat the current workaround?','explanation':'The narrower target is a hypothesis. Test a reversed decision and current owner before treating it as a validated product opportunity.','finding_ids':['problem-v1-F2','skeptic-v1-F2']}],
      'next_experiment':'Test five team leads on finding the latest decision and owner from three meeting records containing one reversed decision. Compare completion time, wrong answers and corrections against their existing method. Decide an acceptance threshold before running the test.'},c)
    c['events']=[{'seq':1,'time':now(),'role':'system','action':'sample_loaded','detail':'Curated worked example loaded. No live search or model call was performed.'}]
    return c
