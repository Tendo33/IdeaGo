-- Quota management functions for atomic usage tracking.
-- Run this in Supabase Dashboard > SQL Editor.

-- Plan limits lookup: returns the max analyses per month for a plan.
create or replace function public.get_plan_limit(p_plan text)
returns int
language sql
immutable
as $$
  select case p_plan
    when 'free'       then 5
    when 'pro'        then 100
    when 'enterprise' then 10000
    else 5
  end;
$$;

-- Atomically check quota and increment usage_count.
-- Resets the counter if the billing period has elapsed.
-- Returns JSON: { "allowed": bool, "usage_count": int, "plan_limit": int, "plan": text }
create or replace function public.check_and_increment_quota(p_user_id uuid)
returns jsonb
language plpgsql
security definer set search_path = ''
as $$
declare
  v_plan text;
  v_usage int;
  v_reset_at timestamptz;
  v_limit int;
  v_now timestamptz := now();
begin
  select plan, usage_count, usage_reset_at
    into v_plan, v_usage, v_reset_at
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

  -- Reset counter if billing period elapsed
  if v_now >= v_reset_at then
    v_usage := 0;
    v_reset_at := date_trunc('month', v_now at time zone 'utc') + interval '1 month';
    update public.profiles
      set usage_count = 0, usage_reset_at = v_reset_at
      where id = p_user_id;
  end if;

  v_limit := public.get_plan_limit(v_plan);

  if v_usage >= v_limit then
    return jsonb_build_object(
      'allowed', false,
      'usage_count', v_usage,
      'plan_limit', v_limit,
      'plan', v_plan
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
    'plan', v_plan
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
  v_plan text;
  v_usage int;
  v_reset_at timestamptz;
  v_limit int;
  v_now timestamptz := now();
begin
  select plan, usage_count, usage_reset_at
    into v_plan, v_usage, v_reset_at
    from public.profiles
    where id = p_user_id;

  if not found then
    return jsonb_build_object('error', 'profile_not_found');
  end if;

  if v_now >= v_reset_at then
    v_usage := 0;
  end if;

  v_limit := public.get_plan_limit(v_plan);

  return jsonb_build_object(
    'usage_count', v_usage,
    'plan_limit', v_limit,
    'plan', v_plan,
    'reset_at', v_reset_at
  );
end;
$$;
