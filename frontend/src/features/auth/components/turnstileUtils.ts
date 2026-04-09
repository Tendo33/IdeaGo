import type { TFunction } from 'i18next'
import type { TurnstileStatus } from './TurnstilePanel'

export const TURNSTILE_SCRIPT_ID = 'cf-turnstile-script'
export const TURNSTILE_SCRIPT_SRC =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

export function getTurnstileMessage(
  t: TFunction,
  status: TurnstileStatus,
): string {
  switch (status) {
    case 'success':
      return t('auth.turnstileSuccess', 'Verification complete.')
    case 'expired':
      return t('auth.turnstileExpired', 'Verification expired. Please wait for a new check.')
    case 'error':
      return t('auth.turnstileError', 'Verification failed. Retrying...')
    case 'unsupported':
      return t(
        'auth.turnstileConfigMissing',
        'Human verification is not configured yet. Please contact support.',
      )
    default:
      return t('auth.turnstileVerifying', 'Verifying you are human...')
  }
}
