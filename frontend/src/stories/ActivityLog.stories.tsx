import type { Meta, StoryObj } from '@storybook/react'
import { ActivityLog } from '../components/ActivityLog'
import type { ActivityLogEntry } from '@/lib/api'

const meta = {
  title: 'Components/ActivityLog',
  component: ActivityLog,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ActivityLog>

export default meta
type Story = StoryObj<typeof meta>

const sampleEntries: ActivityLogEntry[] = [
  {
    timestamp: new Date().toISOString(),
    step: 'input',
    message: 'User selected Apple Inc. (AAPL)',
  },
  {
    timestamp: new Date(Date.now() + 1000).toISOString(),
    step: 'cache',
    message: 'Checking cache for existing analysis...',
  },
  {
    timestamp: new Date(Date.now() + 2000).toISOString(),
    step: 'researcher',
    message: 'Fetching data from 6 MCP servers',
  },
  {
    timestamp: new Date(Date.now() + 5000).toISOString(),
    step: 'financials',
    message: 'Retrieved financial statements',
  },
  {
    timestamp: new Date(Date.now() + 6000).toISOString(),
    step: 'valuation',
    message: 'Retrieved valuation metrics',
  },
  {
    timestamp: new Date(Date.now() + 7000).toISOString(),
    step: 'analyzer',
    message: 'Synthesizing SWOT analysis',
  },
  {
    timestamp: new Date(Date.now() + 10000).toISOString(),
    step: 'critic',
    message: 'Reviewing analysis for accuracy',
  },
  {
    timestamp: new Date(Date.now() + 12000).toISOString(),
    step: 'editor',
    message: 'Formatting final output',
  },
  {
    timestamp: new Date(Date.now() + 14000).toISOString(),
    step: 'output',
    message: 'Analysis complete!',
  },
]

export const Empty: Story = {
  args: {
    entries: [],
  },
}

export const WithEntries: Story = {
  args: {
    entries: sampleEntries,
  },
}

export const InProgress: Story = {
  args: {
    entries: sampleEntries.slice(0, 5),
  },
}

export const WithError: Story = {
  args: {
    entries: [
      ...sampleEntries.slice(0, 4),
      {
        timestamp: new Date(Date.now() + 8000).toISOString(),
        step: 'error',
        message: 'Failed to fetch data from news server',
      },
    ],
  },
}

export const CustomWidth: Story = {
  args: {
    entries: sampleEntries,
    className: 'w-96',
  },
}
