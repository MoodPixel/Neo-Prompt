"""indexed sequential caption jobs with resumable cooperative pause.

No global GPU scheduler. Every inference is protected by the existing vision lock.
"""
from __future__ import annotations
import asyncio
from contextlib import AsyncExitStack
from time import monotonic
import csv
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL
from .images import image_path, ImageError
from .storage import timestamp
from .vision import caption_image
from .generation import ProviderFailure

# Historical compatibility only. The API and frontend impose no total-image cap.
MAX_BATCH_ITEMS = None


def new_job(image_ids, profile, *, notes='', trigger='', options=None, mode='dataset', category='Batch Library', workflow_id=''):
    if mode not in ('dataset','library'):raise ValueError('Unsupported batch destination')
    return {'id':uuid4().hex,'mode':mode,'when':timestamp(),'updated_at':timestamp(),
        'status':'queued','profile_id':profile['id'],'profile_name':profile['name'],'notes':notes,
        'trigger':trigger,'category':category,'options':options or {}, 'workflow_id': workflow_id,
        'shutdown_enabled':False,'shutdown_state':'disabled','shutdown_deadline':None,'items':[{'image_id':x,'status':'queued',
        'text':'','error':'','warnings':[],'attempts':0,'quality_status':'ready',
        'review_approved':False,'runtime_model':None} for x in image_ids]}


def job_progress(job):
    if 'counts' in job and 'total' in job:return job
    result={k:job[k] for k in ('id','when','updated_at','status','profile_name','notes','trigger')}
    result['mode']=job.get('mode','dataset');result['items']=job['items']
    result['counts']={key:sum(x['status']==key for x in job['items']) for key in ('queued','running','completed','failed','interrupted','cancelled')}
    result['total']=len(job['items'])
    result['exportable']=any(x['status']=='completed' and (x.get('quality_status')!='needs_review' or x.get('review_approved')) for x in job['items'])
    result['shown']=len(job['items']);result['offset']=0
    return result


def _save_library(store, job_id, image_id, output, approved=False):
    saved_id=uuid5(NAMESPACE_URL,'neo-prompt-batch-library:'+job_id+':'+image_id).hex
    job = store.batch_header(job_id) or {}
    group = job.get('category', 'Batch Library')
    source = store.image(image_id) or {}
    from pathlib import Path
    filename = Path(source.get('source_name') or source.get('name') or 'Image').stem
    record = {'id':saved_id,'when':timestamp(),'image_id':image_id,'task':'library',
        'text':output['text'],'warnings':output.get('warnings',[]),
        'origin':'batch_library','batch_id':job_id,'review_approved':approved,
        'category':group, 'name':group + ' - ' + filename[:55]}
    store.organize_library_entry('captions', record, idempotent=True)
    return saved_id


async def run_job(store,job_id,vision_lock,profile,comfy_workflow=None):
    store.update_batch(job_id,lambda j:j.update(status='running'))
    async with AsyncExitStack() as stack:
        comfy_session = None
        if profile.get('kind') == 'comfyui' and comfy_workflow is not None:
            from .comfy_adapter import ComfyBatchSession
            comfy_session = await stack.enter_async_context(ComfyBatchSession(profile, comfy_workflow))
        await _process_items(store,job_id,vision_lock,profile,comfy_workflow,comfy_session)


async def _process_items(store,job_id,vision_lock,profile,comfy_workflow,comfy_session):
    while True:
        job=store.batch_header(job_id)
        if not job or job['status'] not in ('running','cancel_requested','pause_requested'):return
        if job['status']=='cancel_requested':
            store.bulk_item_status(job_id,('queued',),'cancelled')
            store.update_batch(job_id,lambda j:j.update(status='cancelled'))
            return
        if job['status']=='pause_requested':
            store.update_batch(job_id,lambda j:j.update(status='paused'))
            return
        choice=store.next_batch_item(job_id)
        if choice is None:
            summary=store.batch(job_id,limit=0)
            failed=summary['counts'].get('failed',0) or summary['counts'].get('interrupted',0)
            store.update_batch(job_id,lambda j:j.update(status='completed_with_errors' if failed else 'completed'))
            return
        idx,item=choice
        store.update_batch_item(job_id,idx,{'status':'running','attempts':item.get('attempts',0)+1,'error':'','warnings':[], 'execution_uncertain':False})
        started=monotonic()
        try:
            path,meta=image_path(store,item['image_id'])
            async with vision_lock:
                mode=job.get('mode','dataset')
                effective=dict(job.get('options') or {})
                effective['output_format']='dataset_caption' if mode=='dataset' else (effective.get('output_format') if effective.get('output_format') in ('descriptive_caption','alt_text','tags_keywords','attribute_list') else 'descriptive_caption')
                caption_kwargs={'comfy_session':comfy_session} if comfy_session is not None else {}
                output=await caption_image(profile,path,meta['mime'],task=mode,instruction=job['notes'],trigger=job['trigger'] if mode=='dataset' else '',options=effective,comfy_workflow=comfy_workflow,**caption_kwargs)
            saved=''
            if mode=='library' and output.get('quality_status','ready')=='ready':
                saved=_save_library(store,job_id,item['image_id'],output)
            store.update_batch_item(job_id,idx,{'status':'completed','text':output['text'],'error':'',
                'warnings':output['warnings'],'saved_caption_id':saved,'quality_status':output.get('quality_status','ready'),
                'review_approved':False,'runtime_model':output.get('runtime_model'),
                'comfy_prompt_id':output.get('comfy_prompt_id'), 'inference_seconds':round(monotonic()-started,2)})
        except (ProviderFailure,ImageError) as exc:
            uncertain=bool(getattr(exc,'execution_uncertain',False)) and profile.get('kind')=='comfyui'
            store.update_batch_item(job_id,idx,{'status':'failed','error':str(getattr(exc,'detail',exc)),
                'execution_uncertain':uncertain,'comfy_prompt_id':getattr(exc,'prompt_id',None),
                'inference_seconds':round(monotonic()-started,2)})
            if uncertain:
                # Remote prompt may still be queued; never submit the remaining files or authorize power-off.
                store.update_batch(job_id,lambda j:j.update(status='interrupted',backend_check_required=True,
                    shutdown_enabled=False,shutdown_state='disarmed_backend_uncertain',shutdown_deadline=None,
                    backend_check_message='ComfyUI may still be running a prompt. Inspect its queue/history before resuming.'))
                return
        except Exception:
            store.update_batch_item(job_id,idx,{'status':'failed','error':'Unexpected processing error; inspect backend diagnostics.',
                'inference_seconds':round(monotonic()-started,2)})
        await asyncio.sleep(0)


def _csv_safe(value):
    value=str(value).replace('\x00','')
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value


def export_zip(store,job):
    """Bounded-memory Zip64 export. CSV is spooled to disk, never held in RAM."""
    export_dir=store.root/'exports';export_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='neo_prompt_dataset_',suffix='.zip',dir=export_dir,delete=False) as f:
        target=Path(f.name)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8-sig',newline='',prefix='neo_prompt_manifest_',suffix='.csv',dir=export_dir,delete=False) as f:
        csv_path=Path(f.name)
    try:
        with csv_path.open('w',newline='',encoding='utf-8-sig') as csv_handle, zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as archive:
            writer=csv.writer(csv_handle);writer.writerow(['image','caption','status','source_path'])
            records=store.iter_batch_items(job['id']) if hasattr(store,'iter_batch_items') else iter(job['items'])
            for n,item in enumerate(records,1):
                if item['status']!='completed' or not item.get('text') or (item.get('quality_status')=='needs_review' and not item.get('review_approved')):continue
                path,meta=image_path(store,item['image_id']);name=f'image_{n:04d}'
                archive.write(path,arcname=f'dataset/{name}{meta["ext"]}')
                archive.writestr(f'dataset/{name}.txt',item['text'])
                writer.writerow([_csv_safe(name+meta['ext']),_csv_safe(item['text']),'completed',_csv_safe(meta.get('relative_path',''))])
            csv_handle.flush()
            archive.write(csv_path,arcname='dataset/manifest.csv')
            archive.writestr('README.txt','Neo Prompt dataset export: approved completed pairs only. Validate captions before training.\n')
        return target
    except Exception:
        target.unlink(missing_ok=True);raise
    finally:
        csv_path.unlink(missing_ok=True)
