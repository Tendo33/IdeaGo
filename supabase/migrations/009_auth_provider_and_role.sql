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
