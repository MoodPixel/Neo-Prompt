"""optional Windows power-off after persisted, terminal Batch jobs.

Power commands are NEVER issued when shutdown is unarmed, while a job is running,
when another job starts, or after an application restart.  A countdown exists
solely in this process; Windows is not given a queued shutdown command.
"""
from __future__ import annotations
import asyncio
import os
import subprocess
from datetime import datetime, timezone, timedelta

COUNTDOWN_SECONDS = 60


def windows_supported():
    return os.name == 'nt'


def _execute_windows_shutdown():
    if not windows_supported():
        raise RuntimeError('Windows auto-shutdown is unavailable on this operating system.')
    # No shell; no /f forced-close flag; shutdown only after the cancellable app countdown.
    subprocess.Popen(['shutdown.exe', '/s', '/t', '0'], shell=False,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True)


class PowerCoordinator:
    def __init__(self, store, *, supported=None, executor=None, countdown=COUNTDOWN_SECONDS):
        self.store = store
        self.supported = windows_supported() if supported is None else supported
        self.executor = executor or _execute_windows_shutdown
        self.countdown = countdown
        self.pending = {}  # job_id -> countdown task; never survives restart

    def disarm_on_startup(self):
        self.store.disarm_orphan_shutdowns()

    def cancel(self, job_id, *, reason='cancelled'):
        job = self.store.batch_header(job_id)
        if not job or job.get('shutdown_state') not in ('armed','countdown'):
            return False
        task = self.pending.pop(job_id, None)
        if task and not task.done():
            task.cancel()
        self.store.update_batch(job_id, lambda j:j.update(shutdown_state=reason, shutdown_deadline=None))
        return True

    def cancel_all(self, *, reason='cancelled_other_job'):
        for job_id in list(self.pending):
            self.cancel(job_id,reason=reason)

    def offer(self, job_id):
        job = self.store.batch_header(job_id)
        if not job or not self.supported or job.get('backend_check_required') or not job.get('shutdown_enabled') or job.get('shutdown_state') != 'armed':
            return False
        if job.get('status') not in ('completed', 'completed_with_errors'):
            return False
        summary = self.store.batch(job_id,limit=0)
        if not summary or any(summary['counts'].get(s,0) for s in ('queued','running','interrupted')):
            return False
        if job_id in self.pending:
            return False
        deadline = (datetime.now(timezone.utc)+timedelta(seconds=self.countdown)).isoformat()
        self.store.update_batch(job_id,lambda j:j.update(shutdown_state='countdown',shutdown_deadline=deadline))
        task = asyncio.create_task(self._countdown_then_shutdown(job_id))
        self.pending[job_id] = task
        return True

    async def _countdown_then_shutdown(self, job_id):
        try:
            await asyncio.sleep(self.countdown)
            job=self.store.batch_header(job_id)
            summary=self.store.batch(job_id,limit=0)
            if not job or not summary or job.get('backend_check_required') or job.get('shutdown_state')!='countdown' or not job.get('shutdown_enabled'):
                return
            if job.get('status') not in ('completed', 'completed_with_errors'):
                return
            if any(summary['counts'].get(s,0) for s in ('queued','running','interrupted')):
                return
            self.store.update_batch(job_id,lambda j:j.update(shutdown_state='executing',shutdown_deadline=None))
            try:
                self.executor()
            except Exception as exc:
                self.store.update_batch(job_id,lambda j:j.update(shutdown_state='failed',shutdown_error=str(exc)[:240]))
            else:
                self.store.update_batch(job_id,lambda j:j.update(shutdown_state='command_sent'))
        except asyncio.CancelledError:
            return
        finally:
            self.pending.pop(job_id,None)
