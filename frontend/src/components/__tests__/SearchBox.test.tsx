import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBox } from '../SearchBox'
import i18n from '../../i18n'

const inputLabel = i18n.t('search.placeholder')
const submitLabel = i18n.t('search.button')
const minimumHint = i18n.t('search.tooShort', { min: 5, current: 0 })

describe('SearchBox', () => {
  it('renders input and submit button', () => {
    render(<SearchBox onSubmit={() => {}} />)
    expect(screen.getByLabelText(inputLabel)).toBeInTheDocument()
    expect(screen.getByLabelText(submitLabel)).toBeInTheDocument()
    expect(screen.getByText(minimumHint)).toBeInTheDocument()
  })

  it('disables submit when query is too short', () => {
    render(<SearchBox onSubmit={() => {}} />)
    const btn = screen.getByLabelText(submitLabel)
    expect(btn).toBeDisabled()

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: 'ab' } })
    expect(btn).toBeDisabled()
  })

  it('enables submit when query is >= 5 chars', () => {
    render(<SearchBox onSubmit={() => {}} />)
    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: 'Hello world idea' } })
    expect(screen.getByLabelText(submitLabel)).not.toBeDisabled()
  })

  it('sets maxLength to 1000', () => {
    render(<SearchBox onSubmit={() => {}} />)
    expect(screen.getByLabelText(inputLabel)).toHaveAttribute('maxLength', '1000')
  })

  it('calls onSubmit with trimmed query on form submit', () => {
    const onSubmit = vi.fn()
    render(<SearchBox onSubmit={onSubmit} />)

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: '  A markdown editor app  ' } })
    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).toHaveBeenCalledWith('A markdown editor app')
  })

  it('does not call onSubmit when query is too short', () => {
    const onSubmit = vi.fn()
    render(<SearchBox onSubmit={onSubmit} />)

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: 'ab' } })
    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('does not call onSubmit when query is too long', () => {
    const onSubmit = vi.fn()
    render(<SearchBox onSubmit={onSubmit} />)

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: 'a'.repeat(1001) } })
    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByLabelText(submitLabel)).toBeDisabled()
  })

  it('shows loading state', () => {
    render(<SearchBox onSubmit={() => {}} isLoading />)
    const input = screen.getByLabelText(inputLabel)
    expect(input).toBeDisabled()
    expect(screen.getByText(i18n.t('search.submittingHint'))).toBeInTheDocument()
  })
})
