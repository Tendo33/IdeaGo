-- Combined Supabase migrations for fresh project bootstrap.
-- Execute this whole file in Supabase Dashboard > SQL Editor.
-- Order preserved from 001 through 012.
-- Current baseline:
-- - Billing UI is disabled in the app
-- - Signed-in users are limited to 5 analyses per day

-- ============================================================================
-- 001_create_profiles.sql
-- ============================================================================

-- Profiles table: extends auth.users with app-specific data.
-- Legacy billing columns/plan metadata are preserved for compatibility,
-- but the active quota model is now a flat daily limit for signed-in users.
-- Run this in Supabase Dashboard > SQL Editor.

create table if not exists public.profiles (
  id uuid references auth.users on delete cascade primary key,
  display_name text not null default '',
  avatar_url text not null default '',
  bio text not null default '',
  plan text not null default 'free' check (plan in ('free', 'pro', 'enterprise')),
  usage_count int not null default 0,
  usage_reset_at timestamptz not null default date_trunc('day', now() at time zone 'utc') + interval '1 day',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Row Level Security
alter table public.profiles enable row level security;

create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', ''),
    coalesce(new.raw_user_meta_data ->> 'avatar_url', '')
  );
  return new;
end;
$$;

-- ============================================================================
-- 015_admin_quota_override.sql
-- ============================================================================

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS plan_limit_override int
  CHECK (plan_limit_override IS NULL OR plan_limit_override >= 0);

CREATE OR REPLACE FUNCTION public.check_and_increment_quota(p_user_id uuid)
returns jsonb
language plpgsql
security definer set search_path = ''
as $$
declare
  v_usage int;
  v_reset_at timestamptz;
  v_limit int;
  v_limit_override int;
  v_now timestamptz := now();
begin
  select usage_count, usage_reset_at, plan_limit_override
    into v_usage, v_reset_at, v_limit_override
    from public.profiles
    where id = p_user_id
    for update;

  if not found then
    return jsonb_build_object(
      'allowed', false,
      'usage_count', 0,
      'plan_limit', 0,
      'plan', 'unknown',
      'error', 'profile_not_found'
    );
  end if;

  if v_now >= v_reset_at then
    v_usage := 0;
    v_reset_at := date_trunc('day', v_now at time zone 'utc') + interval '1 day';
    update public.profiles
      set usage_count = 0, usage_reset_at = v_reset_at
      where id = p_user_id;
  end if;

  v_limit := coalesce(v_limit_override, public.get_plan_limit('daily'));

  if v_usage >= v_limit then
    return jsonb_build_object(
      'allowed', false,
      'usage_count', v_usage,
      'plan_limit', v_limit,
      'plan', 'daily'
    );
  end if;

  update public.profiles
    set usage_count = v_usage + 1
    where id = p_user_id;

  return jsonb_build_object(
    'allowed', true,
    'usage_count', v_usage + 1,
    'plan_limit', v_limit,
    'plan', 'daily'
  );
end;
$$;

CREATE OR REPLACE FUNCTION public.get_quota_info(p_user_id uuid)
returns jsonb
language plpgsql
stable
security definer set search_path = ''
as $$
declare
  v_usage int;
  v_reset_at timestamptz;
  v_limit int;
  v_limit_override int;
  v_now timestamptz := now();
begin
  select usage_count, usage_reset_at, plan_limit_override
    into v_usage, v_reset_at, v_limit_override
    from public.profiles
    where id = p_user_id;

  if not found then
    return jsonb_build_object('error', 'profile_not_found');
  end if;

  if v_now >= v_reset_at then
    v_usage := 0;
  end if;

  v_limit := coalesce(v_limit_override, public.get_plan_limit('daily'));

  return jsonb_build_object(
    'usage_count', v_usage,
    'plan_limit', v_limit,
    'plan', 'daily',
    'reset_at', v_reset_at
  );
end;
$$;

-- ============================================================================
-- 016_admin_profile_indexes.sql
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_profiles_created_at_desc
  ON public.profiles (created_at DESC);

-- ============================================================================
-- 013_plan_breakdown_rpc.sql
-- ============================================================================

-- Aggregate plan breakdown for admin dashboard without full-table scans via REST.
CREATE OR REPLACE FUNCTION public.get_plan_breakdown()
RETURNS TABLE(plan text, count int)
LANGUAGE sql
STABLE
SECURITY DEFINER SET search_path = ''
AS $$
  SELECT
    COALESCE(NULLIF(p.plan, ''), 'free') AS plan,
    COUNT(*)::int AS count
  FROM public.profiles p
  GROUP BY COALESCE(NULLIF(p.plan, ''), 'free')
  ORDER BY count DESC;
$$;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Auto-update updated_at timestamp
create or replace function public.update_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.update_updated_at();

-- ============================================================================
-- 002_quota_functions.sql
-- ============================================================================

-- Quota management functions for atomic usage tracking.
-- Run this in Supabase Dashboard > SQL Editor.

-- Daily limit lookup: all signed-in users currently share the same daily quota.
create or replace function public.get_plan_limit(p_plan text)
returns int
language sql
immutable
as $$
  select 5;
$$;

-- Atomically check quota and increment usage_count.
-- Resets the counter if the daily window has elapsed.
-- Returns JSON: { "allowed": bool, "usage_count": int, "plan_limit": int, "plan": text }
create or replace function public.check_and_increment_quota(p_user_id uuid)
returns jsonb
language plpgsql
security definer set search_path = ''
as $$
declare
  v_usage int;
  v_reset_at timestamptz;
  v_limit int;
  v_now timestamptz := now();
begin
  select usage_count, usage_reset_at
    into v_usage, v_reset_at
    from public.profiles
    where id = p_user_id
    for update;

  if not found then
    return jsonb_build_object(
      'allowed', false,
      'usage_count', 0,
      'plan_limit', 0,
      'plan', 'unknown',
      'error', 'profile_not_found'
    );
  end if;

  -- Reset counter if the daily window elapsed
  if v_now >= v_reset_at then
    v_usage := 0;
    v_reset_at := date_trunc('day', v_now at time zone 'utc') + interval '1 day';
    update public.profiles
      set usage_count = 0, usage_reset_at = v_reset_at
      where id = p_user_id;
  end if;

  v_limit := public.get_plan_limit('daily');

  if v_usage >= v_limit then
    return jsonb_build_object(
      'allowed', false,
      'usage_count', v_usage,
      'plan_limit', v_limit,
      'plan', 'daily'
    );
  end if;

  -- Increment
  update public.profiles
    set usage_count = v_usage + 1
    where id = p_user_id;

  return jsonb_build_object(
    'allowed', true,
    'usage_count', v_usage + 1,
    'plan_limit', v_limit,
    'plan', 'daily'
  );
end;
$$;

-- Read-only quota info (no increment, no lock).
create or replace function public.get_quota_info(p_user_id uuid)
returns jsonb
language plpgsql
stable
security definer set search_path = ''
as $$
declare
  v_usage int;
  v_reset_at timestamptz;
  v_limit int;
  v_now timestamptz := now();
begin
  select usage_count, usage_reset_at
    into v_usage, v_reset_at
    from public.profiles
    where id = p_user_id;

  if not found then
    return jsonb_build_object('error', 'profile_not_found');
  end if;

  if v_now >= v_reset_at then
    v_usage := 0;
  end if;

  v_limit := public.get_plan_limit('daily');

  return jsonb_build_object(
    'usage_count', v_usage,
    'plan_limit', v_limit,
    'plan', 'daily',
    'reset_at', v_reset_at
  );
end;
$$;

-- ============================================================================
-- 003_create_reports.sql
-- ============================================================================

-- Reports and report status tables: replaces file-based cache.
-- Run this in Supabase Dashboard > SQL Editor.

-- Full research reports
create table if not exists public.reports (
  id text primary key,
  user_id uuid references auth.users on delete set null,
  query text not null default '',
  cache_key text not null default '',
  competitor_count int not null default 0,
  report_data jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_reports_user_id on public.reports (user_id);
create index if not exists idx_reports_cache_key on public.reports (cache_key);
create index if not exists idx_reports_created_at on public.reports (created_at desc);

-- ============================================================================
-- 014_reports_search_indexes.sql
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_reports_user_created_at
  ON public.reports (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_reports_query_trgm
  ON public.reports
  USING gin (query gin_trgm_ops);

-- Row Level Security
alter table public.reports enable row level security;

create policy "Users can view own reports"
  on public.reports for select
  using (auth.uid() = user_id);

create policy "Users can delete own reports"
  on public.reports for delete
  using (auth.uid() = user_id);

-- Service role (backend) can do everything; no extra policy needed.
-- The backend uses service_role key which bypasses RLS.

-- Pipeline run status (ephemeral, cleaned up periodically)
create table if not exists public.report_status (
  report_id text primary key,
  user_id uuid references auth.users on delete set null,
  status text not null default 'processing'
    check (status in ('processing', 'complete', 'failed', 'cancelled')),
  query text not null default '',
  error_code text,
  message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_report_status_user_id on public.report_status (user_id);

alter table public.report_status enable row level security;

create policy "Users can view own report status"
  on public.report_status for select
  using (auth.uid() = user_id);

-- Auto-update updated_at for reports
create or replace trigger reports_updated_at
  before update on public.reports
  for each row execute function public.update_updated_at();

create or replace trigger report_status_updated_at
  before update on public.report_status
  for each row execute function public.update_updated_at();

-- Cleanup function: remove expired reports and status older than N hours.
-- Call from backend scheduled task or cron.
create or replace function public.cleanup_expired_reports(p_ttl_hours int default 24)
returns int
language plpgsql
security definer set search_path = ''
as $$
declare
  v_count int;
begin
  delete from public.reports
    where created_at < now() - make_interval(hours => p_ttl_hours);
  get diagnostics v_count = row_count;

  delete from public.report_status
    where updated_at < now() - make_interval(hours => p_ttl_hours);

  return v_count;
end;
$$;

-- ============================================================================
-- 004_decouple_user_fk_and_harden.sql
-- ============================================================================

-- Migration 004: Decouple business tables from auth.users FK and harden ownership.
--
-- LinuxDo OAuth generates internal UUIDs via uuid5() that do not exist in
-- auth.users. The FK constraints cause silent insert failures, leaving
-- profiles/reports without proper ownership. Removing the FK while keeping
-- the uuid column lets any auth provider store its canonical user ID.
--
-- RLS policies are unchanged - they still reference auth.uid() for
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

-- ============================================================================
-- 005_processing_reports.sql
-- ============================================================================

-- Migration 005: Persistent processing_reports table for distributed dedup.
--
-- Replaces the in-memory _processing_reports dict so that multiple workers /
-- containers share the same dedup state. Each row represents a pipeline
-- slot currently being processed. Rows are removed when the pipeline
-- completes, fails, or is cancelled.
--
-- A stale-row safety net is provided: rows older than 30 minutes are
-- considered abandoned and ignored / cleaned up.

CREATE TABLE IF NOT EXISTS public.processing_reports (
  key            text        PRIMARY KEY,
  report_id      text        NOT NULL,
  user_id        text        NOT NULL DEFAULT '',
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_processing_reports_report_id
  ON public.processing_reports (report_id);

-- Atomically reserve a processing slot.
-- Returns NULL if the slot was successfully reserved (new row inserted).
-- Returns the existing report_id if the slot was already taken.
-- Ignores rows older than 30 minutes (stale safety net).
CREATE OR REPLACE FUNCTION public.reserve_processing_slot(
  p_key       text,
  p_report_id text,
  p_user_id   text DEFAULT ''
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_existing text;
BEGIN
  -- Clean up stale row for this key (older than 30 min)
  DELETE FROM public.processing_reports
    WHERE key = p_key
      AND created_at < now() - interval '30 minutes';

  -- Try to read existing (non-stale) reservation
  SELECT report_id INTO v_existing
    FROM public.processing_reports
    WHERE key = p_key;

  IF v_existing IS NOT NULL THEN
    RETURN v_existing;
  END IF;

  -- Reserve the slot
  INSERT INTO public.processing_reports (key, report_id, user_id)
    VALUES (p_key, p_report_id, p_user_id)
    ON CONFLICT (key) DO NOTHING;

  -- Check if we won the race
  SELECT report_id INTO v_existing
    FROM public.processing_reports
    WHERE key = p_key;

  IF v_existing = p_report_id THEN
    RETURN NULL;
  END IF;

  RETURN v_existing;
END;
$$;

-- Release all slots for a given report_id.
CREATE OR REPLACE FUNCTION public.release_processing_slot(p_report_id text)
RETURNS void
LANGUAGE sql
SECURITY DEFINER SET search_path = ''
AS $$
  DELETE FROM public.processing_reports WHERE report_id = p_report_id;
$$;

-- Check if a report_id is currently processing.
CREATE OR REPLACE FUNCTION public.is_report_processing(p_report_id text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER SET search_path = ''
AS $$
  SELECT EXISTS(
    SELECT 1 FROM public.processing_reports
      WHERE report_id = p_report_id
        AND created_at >= now() - interval '30 minutes'
  );
$$;

-- Periodic cleanup: remove all stale slots older than 30 minutes.
CREATE OR REPLACE FUNCTION public.cleanup_stale_processing_slots()
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_count int;
BEGIN
  DELETE FROM public.processing_reports
    WHERE created_at < now() - interval '30 minutes';
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$;

-- ============================================================================
-- 006_report_retention.sql
-- ============================================================================

-- Migration 006: SaaS report retention.
--
-- User-owned reports should persist indefinitely (or per plan policy).
-- Only anonymous / unowned reports expire via TTL.
--
-- Adds `expires_at` column and rewrites cleanup_expired_reports to use it.

-- 1. Add nullable expires_at column (NULL = never expires)
ALTER TABLE public.reports
  ADD COLUMN IF NOT EXISTS expires_at timestamptz;

-- 2. Backfill: mark existing user-owned reports as non-expiring,
--    and set a 24h expiry for unowned reports.
UPDATE public.reports
  SET expires_at = NULL
  WHERE user_id IS NOT NULL;

UPDATE public.reports
  SET expires_at = created_at + interval '24 hours'
  WHERE user_id IS NULL AND expires_at IS NULL;

-- 3. Index for cleanup query
CREATE INDEX IF NOT EXISTS idx_reports_expires_at
  ON public.reports (expires_at)
  WHERE expires_at IS NOT NULL;

-- 4. Replace cleanup function to use expires_at instead of blanket TTL
CREATE OR REPLACE FUNCTION public.cleanup_expired_reports(p_ttl_hours int default 24)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_count int;
BEGIN
  DELETE FROM public.reports
    WHERE expires_at IS NOT NULL
      AND expires_at < now();
  GET DIAGNOSTICS v_count = ROW_COUNT;

  DELETE FROM public.report_status
    WHERE updated_at < now() - make_interval(hours => p_ttl_hours)
      AND user_id IS NULL;

  RETURN v_count;
END;
$$;

-- ============================================================================
-- 007_stripe_customer.sql
-- ============================================================================

-- Migration 007: Add Stripe customer and subscription IDs to profiles.
--
-- These columns link each user to their Stripe customer/subscription
-- so the backend can manage checkout, billing portal, and plan changes.

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS stripe_customer_id text,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_stripe_customer_id
  ON public.profiles (stripe_customer_id)
  WHERE stripe_customer_id IS NOT NULL;

-- ============================================================================
-- 008_harden_cleanup_and_rls.sql
-- ============================================================================

-- Migration 008: Security hardening - cleanup guard + processing_reports RLS.
--
-- 1. Harden cleanup_expired_reports to never delete user-owned reports.
--    The previous function relied solely on expires_at. If a bug leaves
--    expires_at non-NULL on a user-owned report, the function would delete it.
--    Adding an explicit user_id IS NULL guard provides defense-in-depth.
--
-- 2. Enable RLS on processing_reports. This table was created in migration 005
--    without RLS, meaning anyone with the anon key could query/mutate it.
--    Only service_role (backend) should access this table.

CREATE OR REPLACE FUNCTION public.cleanup_expired_reports(p_ttl_hours int default 24)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
DECLARE
  v_count int;
BEGIN
  DELETE FROM public.reports
    WHERE expires_at IS NOT NULL
      AND expires_at < now()
      AND user_id IS NULL;
  GET DIAGNOSTICS v_count = ROW_COUNT;

  DELETE FROM public.report_status
    WHERE updated_at < now() - make_interval(hours => p_ttl_hours)
      AND user_id IS NULL;

  RETURN v_count;
END;
$$;

ALTER TABLE public.processing_reports ENABLE ROW LEVEL SECURITY;

-- No SELECT/INSERT/UPDATE/DELETE policies for anon or authenticated roles.
-- Only service_role (which bypasses RLS) can access this table.

-- ============================================================================
-- 009_auth_provider_and_role.sql
-- ============================================================================

-- Migration 009: Add auth_provider and role columns to profiles.
--
-- auth_provider: distinguishes Supabase-native vs LinuxDo vs future providers.
-- role: enables admin access control (used by require_admin dependency).

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS auth_provider text NOT NULL DEFAULT 'supabase',
  ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'user'
    CHECK (role IN ('user', 'admin'));

-- Backfill: LinuxDo users have uuid5-based IDs (deterministic, version byte = 5).
-- Supabase users have uuid4 IDs (random, version byte = 4).
-- We identify LinuxDo users by checking uuid version byte.
-- uuid5 has version nibble '5' at position 13 (0-indexed in hex string).
UPDATE public.profiles
  SET auth_provider = 'linuxdo'
  WHERE substring(id::text, 15, 1) = '5'
    AND auth_provider = 'supabase';

-- Update handle_new_user trigger to set auth_provider for Supabase signups
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name, avatar_url, auth_provider)
  VALUES (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', ''),
    coalesce(new.raw_user_meta_data ->> 'avatar_url', ''),
    'supabase'
  );
  RETURN new;
END;
$$;

-- ============================================================================
-- 010_processed_webhook_events.sql
-- ============================================================================

-- Migration 010: Stripe webhook idempotency table.
--
-- Records processed Stripe event IDs to prevent duplicate handling.
-- Old entries are cleaned up after 72 hours.

CREATE TABLE IF NOT EXISTS public.processed_webhook_events (
  event_id    text        PRIMARY KEY,
  event_type  text        NOT NULL DEFAULT '',
  processed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_processed_webhook_events_processed_at
  ON public.processed_webhook_events (processed_at);

ALTER TABLE public.processed_webhook_events ENABLE ROW LEVEL SECURITY;

-- Cleanup function: remove events older than 72 hours
CREATE OR REPLACE FUNCTION public.cleanup_old_webhook_events()
RETURNS int
LANGUAGE sql
SECURITY DEFINER SET search_path = ''
AS $$
  WITH deleted AS (
    DELETE FROM public.processed_webhook_events
      WHERE processed_at < now() - interval '72 hours'
    RETURNING 1
  )
  SELECT count(*)::int FROM deleted;
$$;

-- ============================================================================
-- 011_pg_rate_limiter.sql
-- ============================================================================

-- PG-backed rate limiter for multi-process / multi-node deployments.
-- Replaces the in-memory sliding-window rate limiter.

CREATE TABLE IF NOT EXISTS public.rate_limit_hits (
  key     text        NOT NULL,
  hit_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_key_time
  ON public.rate_limit_hits (key, hit_at);

ALTER TABLE public.rate_limit_hits ENABLE ROW LEVEL SECURITY;

-- Atomic sliding-window check: returns TRUE when the request should be REJECTED.
CREATE OR REPLACE FUNCTION public.check_rate_limit(
  p_key            text,
  p_max_requests   int,
  p_window_seconds int
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  cutoff    timestamptz;
  hit_count int;
BEGIN
  cutoff := now() - make_interval(secs => p_window_seconds);

  DELETE FROM rate_limit_hits WHERE key = p_key AND hit_at < cutoff;

  SELECT count(*) INTO hit_count
    FROM rate_limit_hits
   WHERE key = p_key AND hit_at >= cutoff;

  IF hit_count >= p_max_requests THEN
    RETURN true;
  END IF;

  INSERT INTO rate_limit_hits (key, hit_at) VALUES (p_key, now());
  RETURN false;
END;
$$;

-- Periodic cleanup of very old rows (called by cron or app-level task).
CREATE OR REPLACE FUNCTION public.cleanup_rate_limit_hits(p_max_age_seconds int DEFAULT 7200)
RETURNS int
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  removed int;
BEGIN
  DELETE FROM rate_limit_hits
   WHERE hit_at < now() - make_interval(secs => p_max_age_seconds);
  GET DIAGNOSTICS removed = ROW_COUNT;
  RETURN removed;
END;
$$;

-- ============================================================================
-- 012_audit_log.sql
-- ============================================================================

-- 012: Structured audit log for admin actions and security events.
-- Run after 011_pg_rate_limiter.sql.

CREATE TABLE IF NOT EXISTS audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id    text NOT NULL,
    action      text NOT NULL,
    target_type text,
    target_id   text,
    metadata    jsonb DEFAULT '{}',
    ip_address  text,
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON audit_log (action, created_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
-- No anon/authenticated policies: service_role only (backend writes).

-- Cleanup: delete audit entries older than 90 days.
CREATE OR REPLACE FUNCTION cleanup_audit_log(retention_days int DEFAULT 90)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    removed int;
BEGIN
    DELETE FROM audit_log
    WHERE created_at < now() - make_interval(days => retention_days);
    GET DIAGNOSTICS removed = ROW_COUNT;
    RETURN removed;
END;
$$;
