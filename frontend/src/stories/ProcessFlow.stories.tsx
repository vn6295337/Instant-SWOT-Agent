import type { Meta, StoryObj } from '@storybook/react'
import { ProcessFlow } from '../components/ProcessFlow'
import type { MCPStatus } from '@/lib/api'

const meta = {
  title: 'Components/ProcessFlow',
  component: ProcessFlow,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ProcessFlow>

export default meta
type Story = StoryObj<typeof meta>

const emptyMcpStatus: MCPStatus = {
  financials: 'idle',
  valuation: 'idle',
  volatility: 'idle',
  macro: 'idle',
  news: 'idle',
  sentiment: 'idle',
}

const completedMcpStatus: MCPStatus = {
  financials: 'completed',
  valuation: 'completed',
  volatility: 'completed',
  macro: 'completed',
  news: 'completed',
  sentiment: 'completed',
}

const inProgressMcpStatus: MCPStatus = {
  financials: 'completed',
  valuation: 'completed',
  volatility: 'executing',
  macro: 'idle',
  news: 'idle',
  sentiment: 'idle',
}

export const Idle: Story = {
  args: {
    currentStep: '',
    completedSteps: [],
    mcpStatus: emptyMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const InputStep: Story = {
  args: {
    currentStep: 'input',
    completedSteps: [],
    mcpStatus: emptyMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const CheckingCache: Story = {
  args: {
    currentStep: 'cache',
    completedSteps: ['input'],
    mcpStatus: emptyMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const ResearcherActive: Story = {
  args: {
    currentStep: 'researcher',
    completedSteps: ['input', 'cache'],
    mcpStatus: inProgressMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const AnalyzerActive: Story = {
  args: {
    currentStep: 'analyzer',
    completedSteps: ['input', 'cache', 'researcher'],
    mcpStatus: completedMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const CriticActive: Story = {
  args: {
    currentStep: 'critic',
    completedSteps: ['input', 'cache', 'researcher', 'analyzer'],
    mcpStatus: completedMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const EditorActive: Story = {
  args: {
    currentStep: 'editor',
    completedSteps: ['input', 'cache', 'researcher', 'analyzer', 'critic'],
    mcpStatus: completedMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const Completed: Story = {
  args: {
    currentStep: 'output',
    completedSteps: ['input', 'cache', 'researcher', 'analyzer', 'critic', 'editor', 'output'],
    mcpStatus: completedMcpStatus,
    llmProvider: 'Claude 3.5',
  },
}

export const CacheHit: Story = {
  args: {
    currentStep: 'output',
    completedSteps: ['input', 'cache', 'output'],
    mcpStatus: emptyMcpStatus,
    llmProvider: 'Claude 3.5',
    cacheHit: true,
  },
}

export const WithGPT4: Story = {
  args: {
    currentStep: 'analyzer',
    completedSteps: ['input', 'cache', 'researcher'],
    mcpStatus: completedMcpStatus,
    llmProvider: 'GPT-4o',
  },
}
