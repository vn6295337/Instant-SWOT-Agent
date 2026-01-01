import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ActivityLog } from './ActivityLog'
import type { ActivityLogEntry } from '@/lib/api'

describe('ActivityLog', () => {
  const mockEntries: ActivityLogEntry[] = [
    {
      timestamp: '2024-01-15T10:30:00.000Z',
      step: 'input',
      message: 'User selected Tesla, Inc. (TSLA)',
    },
    {
      timestamp: '2024-01-15T10:30:01.000Z',
      step: 'researcher',
      message: 'Fetching data from 6 MCP servers',
    },
    {
      timestamp: '2024-01-15T10:30:05.000Z',
      step: 'analyzer',
      message: 'Synthesizing SWOT analysis',
    },
  ]

  it('renders the Activity Log header', () => {
    render(<ActivityLog entries={[]} />)
    expect(screen.getByText('Activity Log')).toBeInTheDocument()
  })

  it('shows empty state when no entries', () => {
    render(<ActivityLog entries={[]} />)
    expect(screen.getByText(/No activity yet/i)).toBeInTheDocument()
  })

  it('renders log entries', () => {
    render(<ActivityLog entries={mockEntries} />)

    expect(screen.getByText('User selected Tesla, Inc. (TSLA)')).toBeInTheDocument()
    expect(screen.getByText('Fetching data from 6 MCP servers')).toBeInTheDocument()
    expect(screen.getByText('Synthesizing SWOT analysis')).toBeInTheDocument()
  })

  it('displays step labels in brackets', () => {
    render(<ActivityLog entries={mockEntries} />)

    expect(screen.getByText('[input]')).toBeInTheDocument()
    expect(screen.getByText('[researcher]')).toBeInTheDocument()
    expect(screen.getByText('[analyzer]')).toBeInTheDocument()
  })

  it('formats timestamps in local time', () => {
    render(<ActivityLog entries={mockEntries} />)

    // Timestamps should be formatted (exact format depends on locale)
    const timeElements = screen.getAllByText(/\d{1,2}:\d{2}:\d{2}/i)
    expect(timeElements.length).toBeGreaterThan(0)
  })
})
