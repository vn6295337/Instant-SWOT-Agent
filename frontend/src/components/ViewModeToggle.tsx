import { cn } from "@/lib/utils"

export type ViewMode = 'executive' | 'full'

interface ViewModeToggleProps {
  value: ViewMode
  onChange: (mode: ViewMode) => void
  className?: string
}

export function ViewModeToggle({ value, onChange, className }: ViewModeToggleProps) {
  return (
    <div className={cn(
      "inline-flex items-center rounded-lg bg-gray-800 p-1 text-sm",
      className
    )}>
      <button
        onClick={() => onChange('executive')}
        className={cn(
          "px-3 py-1.5 rounded-md transition-all duration-200 font-medium",
          value === 'executive'
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-gray-400 hover:text-gray-200"
        )}
      >
        Executive
      </button>
      <button
        onClick={() => onChange('full')}
        className={cn(
          "px-3 py-1.5 rounded-md transition-all duration-200 font-medium",
          value === 'full'
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-gray-400 hover:text-gray-200"
        )}
      >
        Full
      </button>
    </div>
  )
}

export default ViewModeToggle
