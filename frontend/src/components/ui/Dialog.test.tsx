import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Dialog } from '@/components/ui/Dialog'

describe('Dialog', () => {
  it('keeps focus inside the panel when no focusable children are present', () => {
    const onClose = vi.fn()

    render(
      <Dialog
        open={true}
        onClose={onClose}
        labelledBy="dialog-title"
        panelClassName="border"
      >
        <div>
          <h2 id="dialog-title">Dialog title</h2>
          <p>Read-only content</p>
        </div>
      </Dialog>,
    )

    const dialog = screen.getByRole('dialog', { name: 'Dialog title' })
    expect(dialog).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab' })

    expect(dialog).toHaveFocus()
    expect(onClose).not.toHaveBeenCalled()
  })
})
