import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import {
  User,
  Database,
  Search,
  Brain,
  MessageSquare,
  Edit3,
  FileOutput,
  Server,
  AlertCircle,
} from "lucide-react"
import type { ActivityLogEntry } from "@/lib/api"

interface ActivityLogProps {
  entries: ActivityLogEntry[]
  className?: string
}

const stepIcons: Record<string, React.ElementType> = {
  input: User,
  cache: Database,
  researcher: Search,
  analyzer: Brain,
  critic: MessageSquare,
  editor: Edit3,
  output: FileOutput,
  financials: Server,
  valuation: Server,
  volatility: Server,
  macro: Server,
  news: Server,
  sentiment: Server,
  error: AlertCircle,
}

const stepColors: Record<string, string> = {
  input: 'text-blue-400',
  cache: 'text-yellow-400',
  researcher: 'text-purple-400',
  analyzer: 'text-cyan-400',
  critic: 'text-orange-400',
  editor: 'text-pink-400',
  output: 'text-emerald-400',
  financials: 'text-gray-400',
  valuation: 'text-gray-400',
  volatility: 'text-gray-400',
  macro: 'text-gray-400',
  news: 'text-gray-400',
  sentiment: 'text-gray-400',
  error: 'text-red-400',
}

function formatTimestamp(isoTimestamp: string): string {
  try {
    const date = new Date(isoTimestamp)
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    })
  } catch {
    return '--:--:--'
  }
}

function LogEntry({ entry }: { entry: ActivityLogEntry }) {
  const Icon = stepIcons[entry.step.toLowerCase()] || AlertCircle
  const colorClass = stepColors[entry.step.toLowerCase()] || 'text-gray-400'

  return (
    <div className="flex items-start gap-3 py-2 px-3 hover:bg-gray-800/50 rounded transition-colors">
      <span className="text-xs text-gray-500 font-mono whitespace-nowrap mt-0.5">
        {formatTimestamp(entry.timestamp)}
      </span>
      <div className={cn('mt-0.5', colorClass)}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <span className={cn('text-xs font-medium mr-2', colorClass)}>
          [{entry.step}]
        </span>
        <span className="text-sm text-gray-300">
          {entry.message}
        </span>
      </div>
    </div>
  )
}

export function ActivityLog({ entries, className }: ActivityLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new entries are added
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries])

  return (
    <div className={cn('bg-gray-900/50 border border-gray-800 rounded-xl', className)}>
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          Activity Log
        </h3>
      </div>
      <div
        ref={scrollRef}
        className="max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-gray-900"
      >
        {entries.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500">
            No activity yet. Start an analysis to see real-time updates.
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {entries.map((entry, index) => (
              <LogEntry key={`${entry.timestamp}-${index}`} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default ActivityLog
