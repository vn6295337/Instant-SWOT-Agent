import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ActivityLog } from './ActivityLog'
import type { ActivityLogEntry, MetricEntry } from '@/lib/api'

const baseProps = {
  metrics: [] as MetricEntry[],
  activityLog: [] as ActivityLogEntry[],
  currentStep: 'idle',
  revisionCount: 0,
  score: 0,
}

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
    render(<ActivityLog {...baseProps} />)
    expect(screen.getByText('Activity Log')).toBeInTheDocument()
  })

  it('shows waiting state when no entries', () => {
    render(<ActivityLog {...baseProps} />)
    expect(screen.getByText(/Waiting for input/i)).toBeInTheDocument()
  })

  it('renders activity log entries with step labels', () => {
    render(<ActivityLog {...baseProps} activityLog={mockEntries} />)

    expect(screen.getByText(/\[input\] User selected Tesla, Inc\. \(TSLA\)/)).toBeInTheDocument()
    expect(screen.getByText(/\[researcher\] Fetching data from 6 MCP servers/)).toBeInTheDocument()
    expect(screen.getByText(/\[analyzer\] Synthesizing SWOT analysis/)).toBeInTheDocument()
  })

  it('renders metric entries with source and formatted value', () => {
    const metrics: MetricEntry[] = [
      {
        timestamp: '2024-01-15T10:30:02.000Z',
        source: 'fundamentals',
        metric: 'revenue',
        value: 394300000000,
      } as MetricEntry,
    ]
    render(<ActivityLog {...baseProps} metrics={metrics} />)
    expect(screen.getByText(/\[fundamentals\] revenue: \$394\.3B/)).toBeInTheDocument()
  })

  it('shows the current step in the footer', () => {
    render(<ActivityLog {...baseProps} currentStep="critic" />)
    expect(screen.getByText('Step: critic')).toBeInTheDocument()
  })

  it('formats timestamps in local time', () => {
    render(<ActivityLog {...baseProps} activityLog={mockEntries} />)
    const timeElements = screen.getAllByText(/\d{1,2}:\d{2}:\d{2}/i)
    expect(timeElements.length).toBeGreaterThan(0)
  })
})
