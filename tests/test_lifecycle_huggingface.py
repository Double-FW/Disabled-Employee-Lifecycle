import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from export_huggingface import build
from publish_huggingface import publish
from lifecycle_hf_common import MANAGED,SOURCE,TARGET
from huggingface_hub.errors import EntryNotFoundError

class FakeHub:
    def __init__(self,root):self.files={'.gitattributes':b'preserve me','unrelated.md':b'preserve me too'};self.parent='destination-parent';self.commits=[];self.root=root;self.reject_concurrent=False
    def repo_info(self,**kwargs):return SimpleNamespace(sha=self.parent)
    def download(self,filename,**kwargs):
        if filename not in self.files:raise EntryNotFoundError('Missing test file')
        path=self.root/'old'/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.files[filename]);return str(path)
    def create_commit(self,**kwargs):
        if self.reject_concurrent or kwargs['parent_commit']!=self.parent:raise RuntimeError('Concurrent destination change')
        self.commits.append(kwargs)
        for op in kwargs['operations']:self.files[op.path_in_repo]=op.path_or_fileobj
        self.parent='next-destination-parent'

class LifecycleExport(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.work=Path(self.tmp.name);self.root=self.work/'source';self.output=self.work/'export'
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(ROOT),str(self.root)],check=True)

    def tearDown(self):self.tmp.cleanup()

    def rows(self,name):return [json.loads(l) for l in (self.output/name).read_text().splitlines()]

    def preview(self):return build(self.root,self.output)

    def publish(self,hub,**kw):return publish(self.output,'hf_synthetic_not_a_real_credential',source_root=self.root,api=hub,download=hub.download,check_public=lambda:None,**kw)

    def commit(self):
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Test','-c','user.email=test@example.invalid','add','-A'],check=True)
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Fixture change'],check=True)

    def test_documents_preserve_full_source_and_draft_authority(self):
        report=self.preview();self.assertEqual(7,report['documents'])
        for r in self.rows('documents.jsonl'):
            self.assertEqual((self.root/r['source_path']).read_text(),r['text']);self.assertIn('draft',json.loads(r['authority_context_json'])['qualification'].lower())

    def test_only_managed_files_and_no_report_are_published(self):
        self.preview();self.assertEqual(set(MANAGED),{p.name for p in self.output.iterdir()});self.assertFalse(any('report' in name for name in MANAGED))

    def test_committed_guidance_update_reaches_next_publication(self):
        self.preview();hub=FakeHub(self.work);self.publish(hub)
        p=self.root/'Accessibility in the Employee Lifecycle.md';p.write_text(p.read_text()+'\nAdditional scoped editorial clarification.\n');self.commit();self.preview();self.publish(hub)
        self.assertEqual(2,len(hub.commits));rows=[json.loads(x) for x in hub.files['documents.jsonl'].decode().splitlines()]
        self.assertEqual(p.read_text(),next(x['text'] for x in rows if x['source_path']=='Accessibility in the Employee Lifecycle.md'))

    def test_dataset_name_in_token_field_stops_before_network(self):
        with self.assertRaisesRegex(ValueError,'generated hf_ token'):publish(self.output,TARGET,source_root=self.root,check_public=lambda:self.fail('Network check must not run'))

    def test_same_revision_is_deterministic(self):
        self.preview();other=self.work/'second';build(self.root,other)
        for n in MANAGED:self.assertEqual((self.output/n).read_bytes(),(other/n).read_bytes())

    def test_dirty_canonical_source_stops_export(self):
        p=self.root/'Accessibility in the Employee Lifecycle.md';p.write_text(p.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Working source differs'):self.preview()

    def test_missing_committed_required_source_stops_export(self):
        (self.root/'Accessibility in the Employee Lifecycle.md').unlink();self.commit()
        with self.assertRaisesRegex(ValueError,'committed regular file'):self.preview()

    def test_changed_licence_stops_export(self):
        p=self.root/'LICENSE';p.write_text(p.read_text()+'\nChanged licence.\n');self.commit()
        with self.assertRaisesRegex(ValueError,'Licence bytes changed'):self.preview()

    def test_wrong_destination_stops_before_publish(self):
        self.preview();hub=FakeHub(self.work)
        with self.assertRaisesRegex(ValueError,'HF_DATASET_ID'):self.publish(hub,dataset_id='GarethFW/wrong')
        self.assertEqual([],hub.commits)

    def test_modified_export_cannot_publish(self):
        self.preview();p=self.output/'documents.jsonl';p.write_text(p.read_text()+'\n');hub=FakeHub(self.work)
        with self.assertRaisesRegex(ValueError,'Export bytes differ'):self.publish(hub)
        self.assertEqual([],hub.commits)

    def test_first_publish_is_atomic_and_preserves_other_files(self):
        self.preview();hub=FakeHub(self.work);self.publish(hub)
        self.assertEqual(1,len(hub.commits));self.assertEqual('destination-parent',hub.commits[0]['parent_commit'])
        self.assertEqual(set(MANAGED),{o.path_in_repo for o in hub.commits[0]['operations']});self.assertEqual(b'preserve me',hub.files['.gitattributes'])

    def test_repeat_publish_creates_no_extra_commit(self):
        self.preview();hub=FakeHub(self.work);self.publish(hub);result=self.publish(hub)
        self.assertIn('No changes',result);self.assertEqual(1,len(hub.commits))

    def test_foreign_destination_provenance_is_not_overwritten(self):
        self.preview();hub=FakeHub(self.work);hub.files['provenance.json']=b'{"source_repository":"another/source"}'
        with self.assertRaisesRegex(ValueError,'different source'):self.publish(hub)
        self.assertEqual([],hub.commits)

    def test_concurrent_destination_change_is_not_blindly_retried(self):
        self.preview();hub=FakeHub(self.work);hub.reject_concurrent=True
        with self.assertRaisesRegex(RuntimeError,'Concurrent'):self.publish(hub)
        self.assertEqual([],hub.commits)

    def test_private_source_failure_prevents_destination_write(self):
        self.preview();hub=FakeHub(self.work)
        def private():raise ValueError('Source is private')
        with self.assertRaisesRegex(ValueError,'private'):publish(self.output,'hf_synthetic',source_root=self.root,api=hub,download=hub.download,check_public=private)
        self.assertEqual([],hub.commits)

    def test_whitespace_token_is_rejected_without_echoing_it(self):
        self.preview();token=' accidental-sensitive-token\n'
        with self.assertRaises(ValueError) as raised:publish(self.output,token,source_root=self.root,check_public=lambda:None)
        self.assertNotIn(token.strip(),str(raised.exception))

    def test_new_nested_content_stops_before_destination_write(self):
        p=self.root/'new-guidance/deeper/extra.md';p.parent.mkdir(parents=True);p.write_text('# New substantive content\n');self.commit()
        with self.assertRaisesRegex(ValueError,'New committed content'):self.preview()

    def test_all_source_github_links_survive(self):
        import re
        self.preview();cfg=json.loads((self.root/'huggingface/export-config.json').read_text())
        links=lambda text:set(re.findall(r'https://github\.com/[^\s<>\x22\x27`\\)\]]+',text))
        source=links('\n'.join((self.root/p).read_text() for p in cfg['source_files']))
        exported=links(''.join((self.output/n).read_text() for n in ['documents.jsonl','lifecycle_phases.jsonl','historical_material.jsonl']))
        self.assertTrue(source<=exported)

    def test_source_url_encodes_spaces(self):
        self.preview();r=next(r for r in self.rows('documents.jsonl') if r['source_path']=='Accessibility in the Employee Lifecycle.md')
        self.assertIn('Accessibility%20in%20the%20Employee%20Lifecycle.md',r['source_url']);self.assertNotIn(' ',r['source_url'])


    def test_phases_reconstruct_complete_guide_and_keep_shared_qualifications(self):
        report=self.preview();self.assertEqual(6,report['lifecycle_phases']);rows=self.rows('lifecycle_phases.jsonl')
        self.assertEqual(list(range(1,7)),[r['phase_number'] for r in rows])
        text=rows[0]['shared_guide_prefix']+''.join(r['text'] for r in rows)+rows[0]['shared_guide_suffix']
        self.assertEqual((self.root/'Accessibility in the Employee Lifecycle.md').read_text(),text)
        for r in rows:
            self.assertIn('Status, evidence and use',r['shared_guide_prefix'])
            self.assertIn('Cross-Cutting Requirement: Manager Capability',r['shared_guide_suffix'])
            self.assertFalse(r['empirical_evidence']);self.assertFalse(r['runtime_authority'])

    def test_historical_article_is_complete_separate_and_explicitly_qualified(self):
        report=self.preview();self.assertEqual(1,report['historical_documents'])
        cfg=json.loads((self.root/'huggingface/export-config.json').read_text());path=cfg['historical_files'][0]
        row=self.rows('historical_material.jsonl')[0]
        self.assertEqual(path,row['source_path']);self.assertEqual((self.root/path).read_text(),row['text'])
        self.assertEqual('2025-08-28',row['original_publication_date'])
        self.assertEqual(['opinion_article','ai_conversation_transcript'],row['source_content_types'])
        self.assertFalse(row['empirical_evidence']);self.assertFalse(row['runtime_authority'])
        self.assertIn('not_empirical_evidence',row['record_type'])
        self.assertTrue(all(r['source_path']!=path for n in ['documents.jsonl','lifecycle_phases.jsonl'] for r in self.rows(n)))

    def test_historical_type_cannot_be_silently_promoted(self):
        cfg=json.loads((self.root/'huggingface/export-config.json').read_text());p=self.root/cfg['historical_files'][0]
        p.write_text(p.read_text().replace('status: historical_opinion_and_ai_transcript_not_empirical_evidence','status: verified_findings'));self.commit()
        with self.assertRaisesRegex(ValueError,'Historical opinion/transcript source status'):self.preview()

    def test_new_allowlist_entry_without_role_is_rejected(self):
        p=self.root/'extra.md';p.write_text('# New content\n')
        cfg=self.root/'huggingface/export-config.json';data=json.loads(cfg.read_text());data['source_files'].append('extra.md');cfg.write_text(json.dumps(data));self.commit()
        with self.assertRaisesRegex(ValueError,'needs an explicit export role'):self.preview()

    def test_reviewed_nested_guidance_is_exported_whole(self):
        name='new-guidance/deeper/extra.md';p=self.root/name;p.parent.mkdir(parents=True)
        p.write_text('---\nlicense: MIT\nstatus: editorial_guidance\n---\n\n# Reviewed guidance\n\nComplete source.\n')
        cfg=self.root/'huggingface/export-config.json';data=json.loads(cfg.read_text());data['source_files'].append(name);data['document_files'].append(name);cfg.write_text(json.dumps(data));self.commit()
        result=self.preview();self.assertEqual(8,result['documents'])
        self.assertEqual(p.read_text(),next(r['text'] for r in self.rows('documents.jsonl') if r['source_path']==name))

    def test_missing_phase_stops_export(self):
        p=self.root/'Accessibility in the Employee Lifecycle.md';p.write_text(p.read_text().replace('# Phase 6:','# Phase 9:'));self.commit()
        with self.assertRaisesRegex(ValueError,'six ordered lifecycle phases'):self.preview()

    def test_invented_adoption_stops_export(self):
        p=self.root/'AGENTS.md';p.write_text(p.read_text().replace('adopted_by: null','adopted_by: invented'));self.commit()
        with self.assertRaisesRegex(ValueError,'Local adoption or approval metadata changed'):self.preview()

    def test_dataset_name_does_not_expand_source_scope(self):
        self.preview();card=(self.output/'README.md').read_text()
        self.assertIn('not a general customer-lifecycle framework',card)
        for row in self.rows('documents.jsonl'):self.assertIn('not_general_customer_framework',row['scope'])

class PublicSourceCheck(unittest.TestCase):
    def test_uses_workflow_github_token_for_github_request(self):
        from unittest.mock import patch
        from io import BytesIO
        from lifecycle_hf_common import public_source
        info={'full_name':SOURCE,'private':False,'visibility':'public'}
        with patch.dict('os.environ',{'GITHUB_TOKEN':'synthetic-github-token'}),patch('urllib.request.urlopen',return_value=BytesIO(json.dumps(info).encode())) as call:
            public_source()
            request=call.call_args.args[0]
            self.assertEqual('https://api.github.com/repos/'+SOURCE,request.full_url)
            self.assertEqual('Bearer synthetic-github-token',request.get_header('Authorization'))
    def test_http_error_identifies_source_check_without_sensitive_body(self):
        from unittest.mock import patch
        from io import BytesIO
        from urllib.error import HTTPError
        from lifecycle_hf_common import public_source
        failure=HTTPError('https://api.github.com/repos/'+SOURCE,403,'sensitive response detail',{},BytesIO(b'private response body'))
        with patch('urllib.request.urlopen',side_effect=failure):
            with self.assertRaisesRegex(ValueError,r'Public GitHub source verification failed \(HTTP 403\)') as raised:public_source()
        self.assertNotIn('sensitive',str(raised.exception));self.assertNotIn('private response body',str(raised.exception))
    def test_authenticated_private_source_is_still_blocked(self):
        from unittest.mock import patch
        from io import BytesIO
        from lifecycle_hf_common import public_source
        info={'full_name':SOURCE,'private':True,'visibility':'private'}
        with patch.dict('os.environ',{'GITHUB_TOKEN':'synthetic-github-token'}),patch('urllib.request.urlopen',return_value=BytesIO(json.dumps(info).encode())):
            with self.assertRaisesRegex(ValueError,'approved public'):public_source()


if __name__=='__main__':unittest.main()
