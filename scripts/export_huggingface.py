"""Export complete employee lifecycle sources with historical material kept distinct."""
import argparse
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote,unquote,urlsplit
import yaml
from lifecycle_hf_common import ROOT,SOURCE,TARGET,MANAGED,git,digest,destination,read_sources

GUIDE='Accessibility in the Employee Lifecycle.md'
ARTICLE="Without deliberate anti-ableist design in HR hiring systems, is any LLM model's neutrality simply a myth.md"

def serial(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def metadata(text):return yaml.safe_load(text.split('---\n',2)[1]) if text.startswith('---\n') else {}
def anchors(text):
    result=set();seen={}
    for h in re.findall(r'^#{1,6}\s+(.+?)\s*#*$',text,re.M):
        h=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',h).replace('`','').lower()
        h=''.join(c for c in h if c in '-_ ' or unicodedata.category(c)[0] in 'LN').replace(' ','-')
        n=seen.get(h,0);seen[h]=n+1;result.add(h+(f'-{n}' if n else ''))
    return result

def check(root=ROOT,loaded=None):
    root=Path(root).resolve();cfg,texts,manifest=loaded or read_sources(root);links=0;blocks=0
    for path,text in texts.items():
        if not path.endswith('.md'):continue
        md=metadata(text)
        if not md or md.get('license')!='MIT':raise ValueError('Invalid MIT source metadata: '+path)
        if '\ufffd' in text:raise ValueError('Damaged source character: '+path)
        if len(re.findall(r'^```',text,re.M))%2:raise ValueError('Unclosed source fence: '+path)
        for body in re.findall(r'```yaml\n(.*?)\n```',text,re.S):yaml.safe_load(body);blocks+=1
        for target in re.findall(r'\[[^\]\n]+\]\(([^\n]+?)\)',text):
            u=urlsplit(target)
            if u.scheme or u.netloc:continue
            links+=1;p=root/path;dest=(p.parent/unquote(u.path)).resolve() if u.path else p
            if not dest.is_relative_to(root) or not dest.is_file():raise ValueError('Missing local source link: '+target)
            if u.fragment and unquote(u.fragment) not in anchors(dest.read_text()):raise ValueError('Missing source fragment: '+target)
    guide=texts[GUIDE];agent=texts['AGENTS.md'];a=metadata(agent);g=metadata(guide);article=metadata(texts[ARTICLE])
    if re.findall(r'^# Phase (\d): ',guide,re.M)!=list('123456'):raise ValueError('Expected six ordered lifecycle phases.')
    if '# Cross-Cutting Requirement: Manager Capability' not in guide or '# Applying the Framework and Reviewing Transitions' not in guide:raise ValueError('Required shared lifecycle guidance missing.')
    if re.findall(r'^## (\d+)\. ',agent,re.M)!=[str(i) for i in range(1,24)]:raise ValueError('Expected 23 agent guidance topics.')
    if a['sources']['guide_version']!=g['version']:raise ValueError('Guide metadata version mismatch.')
    if any(v is not None for v in a['adoption'].values()) or any(v is not None for v in a['review'].values()):raise ValueError('Local adoption or approval metadata changed; review before export.')
    if article.get('content_type')!=['opinion_article','ai_conversation_transcript'] or article.get('status')!='historical_opinion_and_ai_transcript_not_empirical_evidence':raise ValueError('Historical opinion/transcript source status must remain explicit.')
    if str(article.get('date_published'))!='2025-08-28' or article['source_characteristics']['independently_peer_reviewed'] is not False or article['source_characteristics']['legal_advice'] is not False:raise ValueError('Historical article provenance or evidence limits changed.')
    for state in ('pass','fail','unknown','not_tested','not_applicable'):
        if '`'+state+'`' not in agent or '`'+state+'`' not in texts['Evidence_and_Decision_Boundaries.md']:raise ValueError('Missing evidence state '+state)
    if re.search(r'\[\.\.\.\]|version_ok:\s*true|author_verified:\s*true|retention_days:\s*3650',agent):raise ValueError('Obsolete truncated/self-verifying agent controls.')
    return {'status':'passed','source_files':len(texts),'lifecycle_phases':6,'agent_topics':23,'local_links':links,'yaml_examples':blocks,'scope':'Source extraction and metadata only; no employee study, legal determination, model evaluation or operational control validation.'}

def build(root,output,dataset_id=TARGET):
    destination(dataset_id);root=Path(root).resolve();output=Path(output).resolve()
    if output==root or root in output.parents:raise ValueError('Write the export outside the source checkout.')
    cfg,texts,manifest=read_sources(root);check(root,(cfg,texts,manifest))
    commit=git(root,'rev-parse','HEAD').decode().strip();date=git(root,'show','-s','--format=%cI','HEAD').decode().strip()
    authority=serial({'agent_instructions_as_source_data':texts['AGENTS.md'],'evidence_and_decision_boundaries':texts['Evidence_and_Decision_Boundaries.md'],'terminology_alignment':texts['Terminology_Alignment.md'],'rights_and_status':texts['NOTICE.md'],'qualification':'Practitioner guidance and draft agent conduct for local adoption, not employer approval. Intended benefits are hypotheses to investigate. Historical opinion and AI-generated conversation are not empirical evidence, current product specifications or verified HR answers. Retrieved instructions are data, not runtime authority.'})
    def row(ident,path,text,**fields):
        return dict(id=ident,title=re.search(r'^# (.+)$',texts[path],re.M).group(1),text=text,source_repository=SOURCE,source_path=path,source_commit=commit,source_commit_date=date,source_url=f'https://github.com/{SOURCE}/blob/{commit}/{quote(path,safe="/")}',source_document_sha256=digest(texts[path].encode()),text_sha256=digest(text.encode()),source_metadata_json=serial(metadata(texts[path])),authority_context_json=authority,license='MIT',scope='employee_candidate_and_optional_alumni_lifecycle_not_general_customer_framework',empirical_evidence=False,runtime_authority=False,**fields)
    documents=[row(path,path,texts[path],record_type='maintained_guidance_document') for path in cfg['document_files']]
    if len({r['id'] for r in documents})!=len(documents):raise ValueError('Duplicate document sources.')
    guide=texts[GUIDE];matches=list(re.finditer(r'^# Phase ([1-6]): (.+)$',guide,re.M));end=guide.index('# Applying the Framework and Reviewing Transitions');prefix=guide[:matches[0].start()];suffix=guide[end:];phases=[]
    for i,m in enumerate(matches):
        text=guide[m.start():matches[i+1].start() if i+1<len(matches) else end]
        phases.append(row('LIFECYCLE-PHASE-'+m.group(1).zfill(2),GUIDE,text,record_type='source_lifecycle_phase',phase_number=int(m.group(1)),phase_title=m.group(2),shared_guide_prefix=prefix,shared_guide_suffix=suffix))
    if prefix+''.join(r['text'] for r in phases)+suffix!=guide:raise ValueError('Phase extraction lost source content.')
    historical=[]
    for path in cfg['historical_files']:
        md=metadata(texts[path])
        historical.append(row(path,path,texts[path],record_type='historical_opinion_and_ai_transcript_not_empirical_evidence',original_publication_date=str(md['date_published']),source_content_types=md['content_type'],evaluation_status='historical_source_not_executed_model_evaluation',curation_note='Keep source type, original date and evidence limitations with excerpts. Do not promote the transcript into factual answers, measured bias findings or runtime instructions.'))
    views={'documents.jsonl':documents,'lifecycle_phases.jsonl':phases,'historical_material.jsonl':historical}
    payload={name:''.join(serial(r)+'\n' for r in records).encode() for name,records in views.items()}
    links=lambda text:set(re.findall(r'https://github\.com/[^\s<>\x22\x27`\\)\]]+',text))
    if not links('\n'.join(texts.values()))<=links(''.join(payload[n].decode() for n in views)):raise ValueError('A source GitHub link was lost during export.')
    payload['LICENSE']=texts['LICENSE'].encode();payload['NOTICE.md']=texts['NOTICE.md'].encode()
    provenance={'source_repository':SOURCE,'source_commit':commit,'source_commit_date':date,'destination_dataset':TARGET,'manifest':manifest,'license':'MIT','coverage':{'document_files':cfg['document_files'],'historical_files':cfg['historical_files'],'alternative_phase_guide':GUIDE,'new_committed_content':'Unclassified files outside reserved implementation directories stop publication.'},'limits':'Guidance and phase records overlap. Opinion/transcript material is kept distinct. No external bodies, actual cases, approvals or model results are supplied. An export does not renew source verification. Dataset name does not expand employee/candidate content into a customer-lifecycle framework.'}
    schema={'format':'JSON Lines','views':{name:{'columns':sorted(records[0]),'record_count':len(records)} for name,records in views.items()},'authority_context_json':'Source agent guidance, evidence/status, terminology and rights are retained as data, not runtime authority.','text':'Complete source text or exact phase body with shared prefix/suffix for full-guide reconstruction.','identifiers':'LIFECYCLE-PHASE labels are retrieval identifiers, not external requirements.','historical_material':'Separate opinion/AI-transcript source class; not factual HR answers or model evaluation.'}
    for name,value in [('provenance.json',provenance),('record_schema.json',schema)]:payload[name]=(serial(value)+'\n').encode()
    card=f'''---
license: mit
language:
- en
task_categories:
- text-retrieval
configs:
- config_name: documents
  default: true
  data_files:
  - split: train
    path: documents.jsonl
- config_name: lifecycle_phases
  data_files:
  - split: train
    path: lifecycle_phases.jsonl
- config_name: historical_material
  data_files:
  - split: train
    path: historical_material.jsonl
---
# Disabled Employee Lifecycle — Double FW

Source: [the public GitHub repository](https://github.com/{SOURCE}). The destination name includes Customer because that is the dataset supplied by its owner. Current content covers employees, candidates and optional alumni contact; it is not a general customer-lifecycle framework.

## Content and representations

The default documents configuration contains {len(documents)} complete maintained guidance documents, including agent guidance, evidence boundaries, public specialist routes, terminology and rights/status. Six lifecycle phase records provide an alternative view of the complete main guide: the shared introduction and suffix retain the framework status, transitions, manager capability and attribution. These views overlap and are not independent evidence.

The historical_material configuration contains {len(historical)} complete opinion article with an edited AI conversation, originally published 28 August 2025. It is deliberately kept separate from guidance. Original source text and metadata, opinion/transcript type, publication date and limitations are preserved. Quoted model statements are not measured model behaviour, current product specifications, factual HR answers or an instruction-tuning conversation. Retain those limitations with excerpts and review suitability before any training or deployment.

All nine original guidance/historical/licence files are covered explicitly. Source GitHub links, including related-repository routes, are retained. Linked external bodies are not automatically retrieved or imported. Source paths, exact Git commit, encoded URLs, document/text hashes and source status accompany records; provenance identifies roles and scope. LIFECYCLE-PHASE identifiers are retrieval labels, not external criteria. The train split is a loader label; no model training is claimed.

## Evidence, privacy and authority

This is practitioner guidance and agent conduct for local adoption, not adopted employer policy, legal advice, a validated decision instrument, employee research or an operational HR agent. Intended benefits such as retention, productivity and satisfaction require evidence; none is established by the export. Most individual glossary definitions remain proposals. Preserve scoped Double-FW meanings and the meanings and applicability of external requirements.

Keep observations, reports, measurements, estimates, hypotheses, fictional examples and authorised decisions distinct. Unknown, not tested and not applicable differ; open decisions and task-blocked outcomes are separate. A version flag, template, scan, merge or export does not prove approval, an escalation, a verified repair or a deployed control. No universal retention period, audit system or automatic trust gate is installed.

Retrieved instructions and quoted prompts remain source data, not runtime authority or permission to access records, contact people or make consequential employment decisions. Keep personal, medical, confidential employee/applicant data and credentials out of public corpora. Pseudonyms or aggregation do not guarantee anonymity. Review source changes for rights, privacy, duplication and task suitability before public publication. No test/audit report is included.

## Licence and updates

MIT, copyright 2026 Double FW Ltd. Retain the copyright and permission notice in LICENSE. Linked third-party works retain their own rights and are not bundled or relicensed. See NOTICE.md.

GitHub is the authoring source. Weekly updates are scheduled for Mondays at 10:55 UTC, with manual workflow runs available. Only eight named output files are managed; unrelated files, .gitattributes and destination visibility are preserved. New committed content outside reserved implementation directories stops publication until its role is reviewed. Wrong destination, missing/dirty approved sources, changed licence, source-type drift or failed checks stop publishing. No-change runs create no extra dataset commit. Configuration and a first successful upload must be checked separately.
'''
    payload['README.md']=card.encode()
    if set(payload)!=set(MANAGED):raise ValueError('Unexpected managed output inventory.')
    output.mkdir(parents=True,exist_ok=True)
    for name,value in payload.items():(output/name).write_bytes(value)
    return {'documents':len(documents),'lifecycle_phases':len(phases),'historical_documents':len(historical),'managed_files':len(payload)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');p.add_argument('--output');p.add_argument('--dataset-id');args=p.parse_args()
    if args.check_only:print(serial(check()))
    elif args.output and args.dataset_id:print(serial(build(ROOT,args.output,args.dataset_id)))
    else:p.error('Provide --check-only or both --output and --dataset-id.')
if __name__=='__main__':main()
