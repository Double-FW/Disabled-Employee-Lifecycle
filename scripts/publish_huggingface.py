"""Publish only the validated managed employee-lifecycle files to the existing fixed dataset."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from export_huggingface import build
from lifecycle_hf_common import ROOT,SOURCE,TARGET,MANAGED,destination,public_source

def publish(folder,token,dataset_id=TARGET,*,source_root=ROOT,api=None,download=None,check_public=public_source):
    destination(dataset_id)
    if not token:raise ValueError('Add the HF_TOKEN repository Actions secret.')
    if token!=token.strip() or any(c in token for c in '\n\r\t'):raise ValueError('HF_TOKEN contains whitespace; replace it with a clean token copy.')
    if not token.startswith("hf_"):raise ValueError("HF_TOKEN must contain the generated hf_ token, not the dataset name.")
    check_public()
    folder=Path(folder)
    # Rebuild against committed source so modified export bytes cannot publish.
    with tempfile.TemporaryDirectory() as temp:
        build(source_root,temp,dataset_id)
        payload={n:(folder/n).read_bytes() for n in MANAGED}
        if any(payload[n]!=(Path(temp)/n).read_bytes() for n in MANAGED):raise ValueError('Export bytes differ from the current validated source snapshot.')
    provenance=json.loads(payload['provenance.json'])
    from huggingface_hub import HfApi,CommitOperationAdd,hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError
    if api is None:api=HfApi(token=token);download=hf_hub_download
    info=api.repo_info(repo_id=TARGET,repo_type='dataset');parent=info.sha
    if not parent:raise ValueError('Destination must be an existing initialised dataset repository.')
    old={}
    for name in MANAGED:
        try:
            p=download(repo_id=TARGET,filename=name,repo_type='dataset',revision=parent,token=token)
            old[name]=Path(p).read_bytes()
        except EntryNotFoundError:old[name]=None
    previous=json.loads(old['provenance.json']) if old['provenance.json'] else {}
    if previous.get('source_repository') not in [None,SOURCE,'https://github.com/'+SOURCE]:raise ValueError('Destination provenance belongs to a different source; no overwrite performed.')
    if all(old[n]==payload[n] for n in MANAGED):return 'No changes; the employee-lifecycle dataset is already up to date.'
    operations=[CommitOperationAdd(path_in_repo=n,path_or_fileobj=payload[n]) for n in MANAGED if old[n]!=payload[n]]
    api.create_commit(repo_id=TARGET,repo_type='dataset',parent_commit=parent,operations=operations,commit_message='Update Double FW employee-lifecycle dataset',commit_description='GitHub source revision: '+provenance['source_commit'])
    return f'Updated {len(operations)} managed dataset files. Unrelated files and destination visibility were preserved.'

def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--dataset-id',required=True);a=p.parse_args()
    try:result=publish(a.folder,os.environ.get('HF_TOKEN'),a.dataset_id)
    except ValueError as e:raise SystemExit(str(e))
    except Exception as e:
        status=getattr(getattr(e,'response',None),'status_code',None)
        raise SystemExit('Employee-lifecycle publishing failed ('+type(e).__name__+', HTTP '+(str(status) if isinstance(status,int) else 'unknown')+'). Check destination access, token scope and concurrent changes. No credential or response body is logged.')
    print(result)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('## Employee-lifecycle dataset sync\n\n'+result+'\n')

if __name__=='__main__':main()
