import { describe, expect, it } from 'vitest'
import { buttonVariants } from './Button'

describe('buttonVariants visual normalization', () => {
  it('uses calmer baseline typography by default', () => {
    const classes = buttonVariants()
    expect(classes).not.toContain('uppercase')
    expect(classes).not.toContain('tracking-widest')
  })
})
