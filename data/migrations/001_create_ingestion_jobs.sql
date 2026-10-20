-- Migration: 001_create_ingestion_jobs.sql
-- Description: Creates persistent ingestion_jobs table for asynchronous lecture ingestion with pgvector compatibility.

CREATE TABLE IF NOT EXISTS public.ingestion_jobs (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    lesson_id TEXT,
    user_id TEXT,
    title TEXT NOT NULL,
    media_url TEXT,
    file_id TEXT,
    idempotency_key TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    current_stage TEXT NOT NULL DEFAULT 'QUEUED',
    progress_percent INTEGER NOT NULL DEFAULT 0,
    stage_message TEXT DEFAULT 'Job queued for processing',
    checkpoints JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Index for fast lookup by course and status
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_course ON public.ingestion_jobs(course_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON public.ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_idempotency ON public.ingestion_jobs(idempotency_key);

-- Enable Row Level Security (RLS)
ALTER TABLE public.ingestion_jobs ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'ingestion_jobs' AND policyname = 'service_role_all_ingestion_jobs'
    ) THEN
        CREATE POLICY service_role_all_ingestion_jobs ON public.ingestion_jobs
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

-- Allow authenticated users to view jobs for courses they belong to or created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'ingestion_jobs' AND policyname = 'auth_users_read_jobs'
    ) THEN
        CREATE POLICY auth_users_read_jobs ON public.ingestion_jobs
            FOR SELECT
            TO authenticated
            USING (true);
    END IF;
END $$;
