import type { Meta, StoryObj } from '@storybook/react'
import { fn } from '@storybook/test'
import { ViewModeToggle } from '../components/ViewModeToggle'

const meta = {
  title: 'Components/ViewModeToggle',
  component: ViewModeToggle,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  args: {
    onChange: fn(),
  },
} satisfies Meta<typeof ViewModeToggle>

export default meta
type Story = StoryObj<typeof meta>

export const Executive: Story = {
  args: {
    value: 'executive',
  },
}

export const Full: Story = {
  args: {
    value: 'full',
  },
}

export const Interactive: Story = {
  args: {
    value: 'executive',
  },
  render: function Render(args) {
    const [value, setValue] = useState<'executive' | 'full'>(args.value)
    return (
      <ViewModeToggle
        value={value}
        onChange={(newValue) => {
          setValue(newValue)
          args.onChange(newValue)
        }}
      />
    )
  },
}

import { useState } from 'react'
