import { getRuntimeConfig } from '@/lib/config/runtime'

/**
 * Whether billing discovery is exposed in the UI.
 *
 * Sourced from runtime config so the flag can be flipped per deployment
 * without rebuilding the bundle. Defaults to off.
 *
 * This is a function, not a const: runtime config is loaded during bootstrap,
 * so a module-level constant would freeze the build-time default.
 */
export function isPricingEnabled(): boolean {
  return getRuntimeConfig().pricingEnabled
}
