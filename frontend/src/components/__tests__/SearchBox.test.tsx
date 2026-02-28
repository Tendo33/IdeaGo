import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBox } from '../SearchBox'
import i18n from '../../i18n'

const inputLabel = i18n.t('search.placeholder')
const submitLabel = i18n.t('search.button')

describe('SearchBox', () => {
  it('renders input and submit button', () => {
    render(<SearchBox onSubmit={() => {}} />)
    expect(screen.getByLabelText(inputLabel)).toBeInTheDocument()
    expect(screen.getByLabelText(submitLabel)).toBeInTheDocument()
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

  it('shows loading state', () => {
    render(<SearchBox onSubmit={() => {}} isLoading />)
    const input = screen.getByLabelText(inputLabel)
    expect(input).toBeDisabled()
  })
})
