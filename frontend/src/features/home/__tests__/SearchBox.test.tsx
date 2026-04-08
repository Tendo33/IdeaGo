import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBox } from '@/features/home/components/SearchBox'
import i18n from '@/lib/i18n/i18n'

const inputLabel = i18n.t('search.placeholder')
const submitLabel = i18n.t('search.button')
const defaultHint = i18n.t('search.example')
const missingLettersHint = 'Please include letters so we can understand the idea you want analyzed.'
const lowSignalHint = 'Please add a bit more meaningful detail instead of short fragments or IDs.'
const symbolHeavyHint = 'Please remove most symbols and describe the idea in words.'

describe('SearchBox', () => {
  it('renders input and submit button', () => {
    render(<SearchBox onSubmit={() => {}} />)
    expect(screen.getByLabelText(inputLabel)).toBeInTheDocument()
    expect(screen.getByLabelText(submitLabel)).toBeInTheDocument()
    expect(screen.getByText(defaultHint)).toBeInTheDocument()
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

  it('shows direct feedback and blocks numeric-only queries', () => {
    const onSubmit = vi.fn()
    render(<SearchBox onSubmit={onSubmit} />)

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: '12345' } })
    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByLabelText(submitLabel)).toBeDisabled()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText(missingLettersHint)).toBeInTheDocument()
  })

  it('shows direct feedback and blocks low-signal fragments', () => {
    const onSubmit = vi.fn()
    render(<SearchBox onSubmit={onSubmit} />)

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: 'a!!!?' } })
    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByLabelText(submitLabel)).toBeDisabled()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText(lowSignalHint)).toBeInTheDocument()
  })

  it('uses the same semantic character threshold as the backend validator', () => {
    const validation = SearchBox.validateQuery('a1!')
    expect(validation.isValid).toBe(false)
    expect(validation.code).toBe('too_short')

    const nearBoundary = SearchBox.validateQuery('abc!!')
    expect(nearBoundary.isValid).toBe(false)
    expect(nearBoundary.code).toBe('low_signal')

    const validBoundary = SearchBox.validateQuery('abcd!')
    expect(validBoundary.isValid).toBe(true)
  })

  it('shows direct feedback and blocks symbol-heavy queries', () => {
    const onSubmit = vi.fn()
    render(<SearchBox onSubmit={onSubmit} />)

    const input = screen.getByLabelText(inputLabel)
    fireEvent.change(input, { target: { value: '----idea----' } })
    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByLabelText(submitLabel)).toBeDisabled()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText(symbolHeavyHint)).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(<SearchBox onSubmit={() => {}} isLoading />)
    const input = screen.getByLabelText(inputLabel)
    expect(input).toBeDisabled()
    expect(screen.getByText(i18n.t('search.submittingHint'))).toBeInTheDocument()
  })
})
