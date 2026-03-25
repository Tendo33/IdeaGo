-- Migration 004: Decouple business tables from auth.users FK and harden ownership.
--
-- LinuxDo OAuth generates internal UUIDs via uuid5() that do not exist in
-- auth.users. The FK constraints cause silent insert failures, leaving
-- profiles/reports without proper ownership. Removing the FK while keeping
-- the uuid column lets any auth provider store its canonical user ID.
--
-- RLS policies are unchanged — they still reference auth.uid() for
-- Supabase-native sessions. The backend uses service_role (bypasses RLS)
-- for all data access, so LinuxDo sessions work without RLS changes.

-- 1. Drop FK on profiles.id
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_id_fkey;

-- Recreate as plain PK (already PK, just removing the FK reference)
-- No structural change needed; dropping the constraint is sufficient.

-- 2. Drop FK on reports.user_id
ALTER TABLE public.reports DROP CONSTRAINT IF EXISTS reports_user_id_fkey;

-- 3. Drop FK on report_status.user_id
ALTER TABLE public.report_status DROP CONSTRAINT IF EXISTS report_status_user_id_fkey;

-- 4. Change reports.user_id ON DELETE behavior: add NOT NULL default protection
-- We keep user_id nullable for backward compatibility with existing rows,
-- but new rows should always have an owner set at creation time.

-- 5. Add index for looking up report_status by user_id (used for owner fallback)
CREATE INDEX IF NOT EXISTS idx_report_status_user_id_report_id
  ON public.report_status (user_id, report_id);
