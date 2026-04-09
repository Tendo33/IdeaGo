-- Migration 015: add admin-manageable quota override while keeping plan_limit as a display contract.

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
