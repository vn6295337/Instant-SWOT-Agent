import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ViewModeToggle } from './ViewModeToggle'

describe('ViewModeToggle', () => {
  it('renders Executive and Full buttons', () => {
    const onChange = vi.fn()
    render(<ViewModeToggle value="executive" onChange={onChange} />)

    expect(screen.getByRole('button', { name: 'Executive' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Full' })).toBeInTheDocument()
  })

  it('highlights the selected mode', () => {
    const onChange = vi.fn()
    const { rerender } = render(<ViewModeToggle value="executive" onChange={onChange} />)

    const executiveBtn = screen.getByRole('button', { name: 'Executive' })
    const fullBtn = screen.getByRole('button', { name: 'Full' })

    expect(executiveBtn).toHaveClass('bg-primary')
    expect(fullBtn).not.toHaveClass('bg-primary')

    rerender(<ViewModeToggle value="full" onChange={onChange} />)

    expect(executiveBtn).not.toHaveClass('bg-primary')
    expect(fullBtn).toHaveClass('bg-primary')
  })

  it('calls onChange when clicking a different mode', () => {
    const onChange = vi.fn()
    render(<ViewModeToggle value="executive" onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Full' }))

    expect(onChange).toHaveBeenCalledWith('full')
  })

  it('calls onChange with executive when clicking Executive', () => {
    const onChange = vi.fn()
    render(<ViewModeToggle value="full" onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Executive' }))

    expect(onChange).toHaveBeenCalledWith('executive')
  })
})
