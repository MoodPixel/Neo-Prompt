"""Atomic, app-owned JSON persistence for profiles, drafts, and events.

Never imports, reads or mutates Neo Studio / Neo Spaces data.
"""
from __future__ import annotations

import json
import sqlite3
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DataStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        from .batch_store import init_db
        self.batch_db = init_db(self.root)
        for folder in ("drafts",):
            (self.root / folder).mkdir(exist_ok=True)

    def _load(self, relative: str, default: dict[str, Any]) -> dict[str, Any]:
        path = self.root / relative
        if not path.exists():
            return default
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ValueError("Unsupported or invalid data schema")
            return value
        except (ValueError, UnicodeError, OSError) as exc:
            raise RuntimeError(f"Unable to read Neo Prompt state: {relative}") from exc

    def _save(self, relative: str, value: dict[str, Any]) -> None:
        dest = self.root / relative
        fd, name = tempfile.mkstemp(prefix=".neo_tmp_", suffix=".json", dir=dest.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, dest)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def comfy_workflows(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load('comfy_workflows.json', {'schema_version':1,'items':[]})['items'])

    def save_comfy_workflow(self, record: dict[str, Any]) -> None:
        with self._lock:
            data = self._load('comfy_workflows.json', {'schema_version':1,'items':[]})
            data['items'] = [x for x in data['items'] if x['id'] != record['id']] + [record]
            self._save('comfy_workflows.json', data)

    def delete_comfy_workflow(self, workflow_id: str) -> bool:
        with self._lock:
            data = self._load('comfy_workflows.json', {'schema_version':1,'items':[]})
            items=[x for x in data['items'] if x['id'] != workflow_id]
            if len(items)==len(data['items']): return False
            data['items']=items
            self._save('comfy_workflows.json',data)
            return True

    def profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load("profiles.json", {"schema_version": 1, "items": []})["items"])

    def put_profile(self, profile: dict[str, Any]) -> None:
        with self._lock:
            state = self._load("profiles.json", {"schema_version": 1, "items": []})
            state["items"] = [p for p in state["items"] if p["id"] != profile["id"]] + [profile]
            self._save("profiles.json", state)

    def delete_profile(self, profile_id: str) -> bool:
        with self._lock:
            state = self._load("profiles.json", {"schema_version": 1, "items": []})
            kept = [p for p in state["items"] if p["id"] != profile_id]
            if len(kept) == len(state["items"]):
                return False
            state["items"] = kept
            self._save("profiles.json", state)
            selections = self.profile_selections()
            for workspace, selected_id in selections.items():
                if selected_id == profile_id:
                    self.save_profile_selection(workspace, "")
            prompt = self.prompt_workspace()
            if prompt.get("profile_id") == profile_id:
                prompt["profile_id"] = ""
                self.save_prompt_workspace(prompt)
            return True

    def profile_selections(self) -> dict[str, str]:
        with self._lock:
            items = self._load("profile_selections.json", {"schema_version": 1, "items": {}})["items"]
            return {name: items.get(name, "") for name in ("caption", "batch")}

    def save_profile_selection(self, workspace: str, profile_id: str) -> None:
        if workspace not in ("caption", "batch"):
            raise ValueError("Unsupported profile-selection workspace")
        with self._lock:
            state = self._load("profile_selections.json", {"schema_version": 1, "items": {}})
            state["items"][workspace] = profile_id
            self._save("profile_selections.json", state)

    def comfy_auto_selections(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._load('comfy_auto_selections.json', {'schema_version':1,'items':{}})['items'])

    def save_comfy_auto_selection(self, workspace: str, profile_id: str, selection: dict) -> None:
        if workspace not in ('prompt','caption','batch'):
            raise ValueError('Unsupported automatic ComfyUI workspace')
        with self._lock:
            state=self._load('comfy_auto_selections.json', {'schema_version':1,'items':{}})
            state['items'][workspace+':'+profile_id]=selection
            self._save('comfy_auto_selections.json',state)

    def draft(self, kind: str) -> dict[str, Any]:
        with self._lock:
            return self._load(f"drafts/{kind}.json", {"schema_version": 1, "kind": kind, "text": "", "task": "", "updated_at": None})

    def save_draft(self, kind: str, text: str, task: str) -> dict[str, Any]:
        with self._lock:
            value = {"schema_version": 1, "kind": kind, "text": text, "task": task, "updated_at": timestamp()}
            self._save(f"drafts/{kind}.json", value)
            return value

    def activities(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load("activity.json", {"schema_version": 1, "items": []})["items"])

    def record_activity(self, entry: dict[str, Any]) -> None:
        with self._lock:
            state = self._load("activity.json", {"schema_version": 1, "items": []})
            state["items"] = ([entry] + state["items"])[:100]
            self._save("activity.json", state)


    # stores are app-owned and additive; earlier saved schemas remain readable.
    def prompt_workspace(self) -> dict[str, Any]:
        with self._lock:
            return self._load("prompt_workspace.json", {"schema_version": 1, "settings": {}})["settings"]

    def save_prompt_workspace(self, settings: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._save("prompt_workspace.json", {"schema_version": 1, "settings": settings})
            return settings

    def prompt_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load("prompt_runs.json", {"schema_version": 1, "items": []})["items"]

    def add_prompt_run(self, run: dict[str, Any]) -> None:
        with self._lock:
            state = self._load("prompt_runs.json", {"schema_version": 1, "items": []})
            state["items"] = ([run] + state["items"])[:100]
            self._save("prompt_runs.json", state)

    def edit_prompt_run(self, run_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            state = self._load("prompt_runs.json", {"schema_version": 1, "items": []})
            for item in state["items"]:
                if item["id"] == run_id:
                    item.update(updates)
                    self._save("prompt_runs.json", state)
                    return dict(item)
            return None

    def record_output_issue(self, *, surface: str, raw: str, issues: list[str], profile_name: str = '') -> None:
        """Private local diagnostics, capped; never returned by general API/list views."""
        with self._lock:
            state = self._load("output_issues.json", {"schema_version": 1, "items": []})
            state['items'] = ([{'when': timestamp(), 'surface': surface,
                                'profile_name': profile_name[:64], 'issues': issues[:10],
                                'raw_response': str(raw)[:16000]}] + state['items'])[:25]
            self._save("output_issues.json", state)

    def library_categories(self) -> list[str]:
        """Categories belong to Neo Prompt, not to a particular Library tab.

        Read old saved categories on demand; this is copy-first, with no migration.
        """
        from .library_organization import category_label
        with self._lock:
            registered = self._load('library_categories.json', {'schema_version': 1, 'items': ['General']})['items']
            saved = self._load('saved_prompts.json', {'schema_version': 1, 'items': []})['items']
            captions = self._load('saved_captions.json', {'schema_version': 1, 'items': []})['items']
            # Index only batch headers; no expensive job-item scanning.
            from .batch_store import connect
            with connect(self.batch_db) as db:
                jobs = db.execute('SELECT data FROM jobs').fetchall()
            discovered = [r.get('category') for r in saved + captions]
            for row in jobs:
                try:
                    discovered.append(json.loads(row['data']).get('category'))
                except (TypeError, ValueError):
                    continue
            unique = {}
            for value in ['General', *registered, *discovered]:
                try:
                    label = category_label(value)
                except ValueError:
                    continue  # Old invalid metadata must not break the registry.
                unique.setdefault(label.casefold(), label)
            return sorted(unique.values(), key=str.casefold)

    def register_library_category(self, value: str) -> tuple[str, bool]:
        """Create a persistent cross-workspace category; case-insensitive idempotence."""
        from .library_organization import category_label
        name = category_label(value)
        with self._lock:
            existing = next((x for x in self.library_categories() if x.casefold() == name.casefold()), None)
            if existing:
                return existing, False
            value = self._load('library_categories.json', {'schema_version': 1, 'items': ['General']})
            value['items'].append(name)
            self._save('library_categories.json', value)
            return name, True

    def saved_prompts(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load("saved_prompts.json", {"schema_version": 1, "items": []})["items"]

    def add_saved_prompt(self, entry: dict[str, Any]) -> None:
        with self._lock:
            state = self._load("saved_prompts.json", {"schema_version": 1, "items": []})
            state["items"] = ([entry] + state["items"])[:250]
            self._save("saved_prompts.json", state)

    def delete_saved_prompt(self, entry_id: str) -> bool:
        with self._lock:
            state = self._load("saved_prompts.json", {"schema_version": 1, "items": []})
            kept = [p for p in state["items"] if p["id"] != entry_id]
            if len(kept) == len(state["items"]):
                return False
            removed = next((p for p in state['items'] if p['id'] == entry_id), None)
            state["items"] = kept
            self._save("saved_prompts.json", state)
            from .library_organization import clear_assets
            clear_assets(self.root, (removed or {}).get('organized_files', []))
            return True

    def prompt_presets(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load("prompt_presets.json", {"schema_version": 1, "items": []})["items"]

    def add_prompt_preset(self, entry: dict[str, Any]) -> None:
        with self._lock:
            state = self._load("prompt_presets.json", {"schema_version": 1, "items": []})
            state["items"] = [p for p in state["items"] if p["id"] != entry["id"]]
            state["items"].insert(0, entry)
            self._save("prompt_presets.json", {"schema_version": 1, "items": state["items"][:100]})

    def delete_prompt_preset(self, entry_id: str) -> bool:
        with self._lock:
            state = self._load("prompt_presets.json", {"schema_version": 1, "items": []})
            kept = [p for p in state["items"] if p["id"] != entry_id]
            if len(kept) == len(state["items"]):
                return False
            self._save("prompt_presets.json", {"schema_version": 1, "items": kept})
            return True

    # images, vision results and durable batch journals remain app-owned.
    def images(self, limit: int | None = None) -> list[dict[str, Any]]:
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            query = 'SELECT data FROM images ORDER BY rowid DESC'
            rows = db.execute(query + (' LIMIT ?' if limit is not None else ''), (limit,) if limit is not None else ()).fetchall()
            return [json.loads(r['data']) for r in rows]

    def image(self, image_id: str) -> dict[str, Any] | None:
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            item = db.execute('SELECT data FROM images WHERE id=?', (image_id,)).fetchone()
            return json.loads(item['data']) if item else None

    def image_by_hash(self, checksum: str) -> dict[str, Any] | None:
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            item = db.execute('SELECT data FROM images WHERE sha256=? LIMIT 1', (checksum,)).fetchone()
            return json.loads(item['data']) if item else None

    def add_image(self, record: dict[str, Any]) -> None:
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            db.execute('INSERT INTO images VALUES (?,?,?)', (record['id'],json.dumps(record),record.get('sha256')))

    def caption_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load('caption_runs.json', {'schema_version': 1, 'items': []})['items']

    def add_caption_run(self, record: dict[str, Any]) -> None:
        with self._lock:
            state = self._load('caption_runs.json', {'schema_version': 1, 'items': []})
            state['items'].insert(0, record)
            self._save('caption_runs.json', state)

    def edit_caption_run(self, run_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            state = self._load('caption_runs.json', {'schema_version':1,'items':[]})
            for item in state['items']:
                if item['id'] == run_id:
                    item.update(updates)
                    self._save('caption_runs.json',state)
                    return dict(item)
            return None

    def saved_captions(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load('saved_captions.json', {'schema_version': 1, 'items': []})['items']

    def save_caption(self, record: dict[str, Any]) -> None:
        with self._lock:
            state = self._load('saved_captions.json', {'schema_version': 1, 'items': []})
            state['items'].insert(0, record)
            self._save('saved_captions.json', state)

    def save_caption_once(self, record: dict[str, Any]) -> bool:
        """Idempotent batch Library save; avoids duplicates across interruptions/retries."""
        with self._lock:
            state = self._load('saved_captions.json', {'schema_version': 1, 'items': []})
            if any(x.get('id') == record['id'] for x in state['items']):
                return False
            state['items'].insert(0, record)
            self._save('saved_captions.json', state)
            return True

    def delete_caption(self, record_id: str) -> bool:
        with self._lock:
            state = self._load('saved_captions.json', {'schema_version': 1, 'items': []})
            kept = [x for x in state['items'] if x['id'] != record_id]
            if len(kept) == len(state['items']):
                return False
            removed = next((x for x in state['items'] if x['id'] == record_id), None)
            self._save('saved_captions.json', {'schema_version': 1, 'items': kept})
            from .library_organization import clear_assets
            clear_assets(self.root, (removed or {}).get('organized_files', []))
            return True

    # separate managed category copies; legacy source records are untouched
    # until the owner expressly saves or edits an entry.
    def organize_library_entry(self, kind: str, record: dict[str, Any], *,
                               update: bool = False, idempotent: bool = False) -> tuple[dict[str, Any], bool]:
        from .library_organization import category_label, entry_name, materialize, clear_assets
        from .images import image_path, ImageError
        if kind not in ('captions', 'prompts'):
            raise ValueError('Invalid Library kind')
        filename = 'saved_captions.json' if kind == 'captions' else 'saved_prompts.json'
        with self._lock:
            state = self._load(filename, {'schema_version': 1, 'items': []})
            current = next((x for x in state['items'] if x['id'] == record['id']), None)
            if idempotent and current is not None:
                return dict(current), False
            if update and current is None:
                raise KeyError('Saved Library entry not found')
            if not update and current is not None:
                raise ValueError('Saved Library identifier already exists')
            merged = dict(current or {})
            merged.update(record)
            merged['category'] = category_label(merged.get('category'))
            merged['name'] = entry_name(merged.get('name') or merged.get('title'), merged['category'])
            if kind == 'prompts':
                merged['title'] = merged['name']
            image = None
            if kind == 'captions':
                try:
                    image, _ = image_path(self, merged['image_id'])
                except ImageError as exc:
                    raise ValueError('Original reference image unavailable; no Library files changed.') from exc
            # Avoid deleting in-place files when changing metadata without moving directories.
            old_files = list((current or {}).get('organized_files', []))
            from .library_organization import relative_assets
            prospective = dict(merged)
            if image is not None:
                prospective['asset_image_ext'] = image.suffix.lower()
            new_files = relative_assets(kind, prospective)
            # If names are unchanged, the content is also unchanged in this endpoint;
            # skip redundant mirror writes and preserve the existing files.
            if current and old_files == new_files and current.get('text') == merged.get('text'):
                merged['organized_files'] = old_files
                state['items'] = [merged if x['id'] == merged['id'] else x for x in state['items']]
                self._save(filename, state)
                return merged, True
            written = materialize(self.root, kind, merged, source_image=image)
            merged['organized_files'] = written
            evicted = []
            if current:
                state['items'] = [merged if x['id'] == merged['id'] else x for x in state['items']]
            else:
                state['items'].insert(0, merged)
                if kind == 'prompts':
                    evicted = state['items'][250:]
                    state['items'] = state['items'][:250]
            try:
                self._save(filename, state)
            except Exception:
                # If paths were shared with an existing record, never remove its files.
                clear_assets(self.root, [x for x in written if x not in old_files])
                raise
            clear_assets(self.root, [x for x in old_files if x not in written])
            for expired in evicted:
                clear_assets(self.root, expired.get('organized_files', []))
            return merged, True

    def rename_library_entry(self, kind: str, item_id: str, *, category: str, name: str) -> dict[str, Any]:
        filename = 'saved_captions.json' if kind == 'captions' else 'saved_prompts.json'
        with self._lock:
            old = next((x for x in self._load(filename, {'schema_version':1, 'items':[]})['items'] if x['id'] == item_id), None)
            if old is None:
                raise KeyError('Saved entry not found')
            updated, _ = self.organize_library_entry(kind, {'id': item_id,
                'category': category, 'name': name or category}, update=True)
            return updated

    def batches(self, limit: int = 25) -> list[dict[str, Any]]:
        from .batch_store import connect, summarize
        with self._lock, connect(self.batch_db) as db:
            rows=db.execute('SELECT * FROM jobs ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
            jobs=[summarize(db,r,0,20) for r in rows]
            legacy=self._load('batches.json',{'schema_version':1,'items':[]})['items']
            return sorted(jobs+[x for x in legacy if x['id'] not in {j['id'] for j in jobs}][:limit],key=lambda x:x.get('when',''),reverse=True)[:limit]

    def add_batch(self, job: dict[str, Any]) -> None:
        from .batch_store import connect, save_job
        with self._lock, connect(self.batch_db) as db:
            save_job(db,job)

    def batch(self, job_id: str, offset: int = 0, limit: int = 30) -> dict[str, Any] | None:
        from .batch_store import connect, summarize
        with self._lock, connect(self.batch_db) as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row:return summarize(db,row,offset,limit)
            old=next((x for x in self._load('batches.json',{'schema_version':1,'items':[]})['items'] if x['id']==job_id),None)
            if old is None:return None
            from .batches import job_progress
            result=job_progress(old)
            result['items']=old['items'][offset:offset+limit]
            result['offset']=offset
            result['shown']=len(result['items'])
            result['exportable']=any(x['status']=='completed' and (x.get('quality_status')!='needs_review' or x.get('review_approved')) for x in old['items'])
            return result

    def promote_legacy_batch(self, job_id: str):
        """Copy a historical JSON batch into indexed queue; keep source journal for rollback."""
        from .batch_store import connect, save_job
        with self._lock:
            old=next((x for x in self._load('batches.json',{'schema_version':1,'items':[]})['items'] if x['id']==job_id),None)
            if not old:return
            with connect(self.batch_db) as db:
                if not db.execute('SELECT 1 FROM jobs WHERE id=?',(job_id,)).fetchone():save_job(db,old)

    def batch_header(self, job_id: str):
        from .batch_store import connect, job_header
        with self._lock, connect(self.batch_db) as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row:return job_header(row)
        return self.batch(job_id,limit=0)

    def batch_item(self, job_id: str, idx: int) -> dict[str, Any] | None:
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            r=db.execute('SELECT data FROM items WHERE job_id=? AND idx=?',(job_id,idx)).fetchone()
            if r:return json.loads(r['data'])
            old=next((x for x in self._load('batches.json',{'schema_version':1,'items':[]})['items'] if x['id']==job_id),None)
            return old['items'][idx] if old and 0<=idx<len(old['items']) else None

    def update_batch_item(self, job_id: str, idx: int, updates: dict) -> dict | None:
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            r=db.execute('SELECT data FROM items WHERE job_id=? AND idx=?',(job_id,idx)).fetchone()
            if r:
                item=json.loads(r['data']); item.update(updates)
                db.execute('UPDATE items SET data=?, status=? WHERE job_id=? AND idx=?',(json.dumps(item),item['status'],job_id,idx))
                db.execute('UPDATE jobs SET updated=? WHERE id=?',(timestamp(),job_id))
                return item
        old=self._load('batches.json', {'schema_version':1,'items':[]})['items']
        return self.update_batch(job_id,lambda j:j['items'][idx].update(updates)) if any(x['id']==job_id for x in old) else None

    def next_batch_item(self, job_id: str):
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            r=db.execute("SELECT idx,data FROM items WHERE job_id=? AND status='queued' ORDER BY idx LIMIT 1",(job_id,)).fetchone()
            if r:return r['idx'],json.loads(r['data'])
        return None

    def iter_batch_items(self, job_id: str):
        from .batch_store import connect
        with connect(self.batch_db) as db:
            rows=db.execute('SELECT data FROM items WHERE job_id=? ORDER BY idx',(job_id,))
            found=False
            for r in rows:
                found=True
                yield json.loads(r['data'])
        if not found:
            old=next((x for x in self._load('batches.json',{'schema_version':1,'items':[]})['items'] if x['id']==job_id),None)
            if old:
                yield from old['items']

    def update_batch(self, job_id: str, updater) -> dict[str, Any] | None:
        # Used for legacy per-job mutations. New jobs only update status/header,
        # never serialize tens of thousands of item entries per item.
        from .batch_store import connect, job_header, summarize
        with self._lock, connect(self.batch_db) as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row:
                head=job_header(row); head['items']=[]
                updater(head)
                head['updated_at']=timestamp()
                meta={k:v for k,v in head.items() if k!='items'}
                db.execute('UPDATE jobs SET data=?, status=?, updated=? WHERE id=?',(json.dumps(meta),head['status'],head['updated_at'],job_id))
                return summarize(db,db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())
            state=self._load('batches.json', {'schema_version': 1, 'items': []})
            for i,job in enumerate(state['items']):
                if job['id']==job_id:
                    updater(job);job['updated_at']=timestamp();state['items'][i]=job;self._save('batches.json',state);return job
            return None

    def bulk_item_status(self, job_id: str, from_states: tuple[str,...], to_state: str):
        from .batch_store import connect
        if not from_states:return 0
        with self._lock, connect(self.batch_db) as db:
            sql="UPDATE items SET data=json_set(data,'$.status', ?,'$.error', ?), status=? WHERE job_id=? AND status IN ("+','.join('?'*len(from_states))+')'
            try:
                row=db.execute(sql,(to_state,'' if to_state=='queued' else '',to_state,job_id,*from_states))
            except sqlite3.OperationalError:
                raise RuntimeError('SQLite JSON1 support is required for resumable batch jobs.')
            return row.rowcount

    def disarm_orphan_shutdowns(self):
        """On every app restart, shutdown authority expires. No delayed OS command survives.

        Only persisted policy fields are changed; generated captions and batch statuses remain.
        """
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            db.execute("""UPDATE jobs SET data=json_set(data,'$.shutdown_state','disarmed_on_restart',
                '$.shutdown_deadline',NULL) WHERE json_extract(data,'$.shutdown_state') IN ('armed','countdown')""")
        with self._lock:
            state=self._load('batches.json',{'schema_version':1,'items':[]})
            changed=False
            for job in state['items']:
                if job.get('shutdown_state') in ('armed','countdown'):
                    job['shutdown_state']='disarmed_on_restart'
                    job['shutdown_deadline']=None
                    changed=True
            if changed:self._save('batches.json',state)

    def interrupt_orphan_batches(self):
        """A previous process cannot continue after a restart. Never fake recovery."""
        from .batch_store import connect
        with self._lock, connect(self.batch_db) as db:
            stale=[r['id'] for r in db.execute("SELECT id FROM jobs WHERE status IN ('running','queued','cancel_requested','pause_requested')")]
            for job_id in stale:
                db.execute("UPDATE jobs SET status='interrupted', updated=? WHERE id=?",(timestamp(),job_id))
                # After an app restart ComfyUI may still execute an accepted remote job.
                # Never auto-resume or enable power-off until the operator checks its queue.
                db.execute("""UPDATE jobs SET data=json_set(data,
                    '$.backend_check_required',json('true'),
                    '$.backend_check_message','Neo Prompt restarted during ComfyUI Batch. Check ComfyUI Queue/History before resuming.',
                    '$.shutdown_enabled',json('false'),
                    '$.shutdown_state','disarmed_on_restart',
                    '$.shutdown_deadline',NULL)
                    WHERE id=? AND (COALESCE(json_extract(data,'$.backend_endpoint'),'') != ''
                      OR COALESCE(json_extract(data,'$.auto_route'),'') != ''
                      OR COALESCE(json_extract(data,'$.workflow_id'),'') != '')""", (job_id,))
        for job_id in stale:
            self.bulk_item_status(job_id,('running','queued'),'interrupted')
        with self._lock:
            state = self._load('batches.json', {'schema_version': 1, 'items': []})
            changed = False
            for job in state['items']:
                if job['status'] in ('running', 'queued', 'cancel_requested'):
                    job['status'] = 'interrupted'
                    if job.get('backend_endpoint') or job.get('auto_route') or job.get('workflow_id'):
                        job.update(backend_check_required=True,
                                   backend_check_message='Neo Prompt restarted during ComfyUI Batch. Check Queue/History before resuming.',
                                   shutdown_enabled=False,shutdown_state='disarmed_on_restart',shutdown_deadline=None)
                    for item in job['items']:
                        if item['status'] in ('running', 'queued'):
                            item['status'] = 'interrupted'
                    job['updated_at'] = timestamp()
                    changed = True
            if changed:
                self._save('batches.json', state)
