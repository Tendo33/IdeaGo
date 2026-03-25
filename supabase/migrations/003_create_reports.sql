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
