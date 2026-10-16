"""SQLite job/image index. App-owned, WAL, indexed per-item updates.

Historical JSON remains intact for compatibility; new job writes never rewrite legacy journals.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .storage import timestamp


def init_db(root: Path):
    path = root / 'batch_index.sqlite3'
    with sqlite3.connect(path, timeout=30) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=30000')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS images (id TEXT PRIMARY KEY, data TEXT NOT NULL, sha256 TEXT);
        CREATE INDEX IF NOT EXISTS idx_images_sha ON images(sha256);
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS items (job_id TEXT NOT NULL, idx INTEGER NOT NULL, image_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL,
          PRIMARY KEY(job_id, idx), FOREIGN KEY(job_id) REFERENCES jobs(id));
        CREATE INDEX IF NOT EXISTS idx_items_queue ON items(job_id,status,idx);
        ''')
        # Copy-only migration of historical image metadata. Preserve old images.json for rollback.
        old = root / 'images.json'
        if old.is_file():
            data = json.loads(old.read_text(encoding='utf-8'))
            for row in data.get('items', []):
                if 'id' in row:
                    db.execute('INSERT OR IGNORE INTO images VALUES (?,?,?)', (row['id'], json.dumps(row), row.get('sha256')))
    return path


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=30000')
    return db


def job_header(row):
    value = json.loads(row['data']);value['status']=row['status'];value['updated_at']=row['updated'];return value


def save_job(db, job):
    meta = {k:v for k,v in job.items() if k!='items'}
    db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (job['id'],json.dumps(meta),job['status'],job['updated_at']))
    db.executemany('INSERT INTO items VALUES (?,?,?,?,?)', ((job['id'],i,item['image_id'],item['status'],json.dumps(item)) for i,item in enumerate(job['items'])))


def summarize(db, row, offset=0, limit=20):
    head=job_header(row)
    counts={key:0 for key in ('queued','running','completed','failed','interrupted','cancelled')}
    for record in db.execute('SELECT status, COUNT(*) qty FROM items WHERE job_id=? GROUP BY status',(head['id'],)):
        counts[record['status']]=record['qty']
    head['counts']=counts
    head['total']=sum(counts.values())
    head['items']=[json.loads(r['data']) for r in db.execute('SELECT data FROM items WHERE job_id=? ORDER BY idx LIMIT ? OFFSET ?', (head['id'],limit,offset))]
    head['offset']=offset
    head['shown']=len(head['items'])
    head['exportable']=db.execute("SELECT 1 FROM items WHERE job_id=? AND status='completed' AND (json_extract(data,'$.quality_status')!='needs_review' OR json_extract(data,'$.review_approved')=1) LIMIT 1",(head['id'],)).fetchone() is not None
    return head
