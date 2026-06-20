CREATE INDEX IF NOT EXISTS idx_printer_scheduler_jobs_due_lookup
ON printer_scheduler_jobs(status, scheduled_for, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_printer_scheduler_jobs_lock_owner
ON printer_scheduler_jobs(lock_owner, locked_at, status);

CREATE INDEX IF NOT EXISTS idx_printer_scheduler_jobs_active_duplicate
ON printer_scheduler_jobs(job_name, job_kind, target_table, target_id, status);
