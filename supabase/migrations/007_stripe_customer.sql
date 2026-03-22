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
