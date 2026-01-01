import React, { useEffect, useRef } from "react"
import { Download } from "lucide-react"
import type { MetricEntry, ActivityLogEntry } from "@/lib/api"

interface UserEvent {
  timestamp: string
  message: string
}

interface MetricsPanelProps {
  metrics: MetricEntry[]
  activityLog: ActivityLogEntry[]
  currentStep: string
  revisionCount: number
  score: number
  isTyping?: boolean
  userEvents?: UserEvent[]
}

function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return ''
  }
}

function formatValue(value: string | number): string {
  if (typeof value === "number") {
    if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
    if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
    if (Math.abs(value) < 100) return value.toFixed(2)
    return value.toLocaleString()
  }
  return String(value)
}

function getCurrentTime(): string {
  return new Date().toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

export function MetricsPanel({
  metrics,
  activityLog,
  currentStep,
  revisionCount,
  score,
  isTyping = false,
  userEvents = [],
}: MetricsPanelProps) {
  const logRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [metrics, activityLog, isTyping, userEvents])

  // Combine and sort all log entries
  const allEntries = React.useMemo(() => {
    const entries: Array<{ time: string; text: string; type: 'metric' | 'activity' | 'user' }> = []

    // Add user events first
    for (const e of userEvents) {
      entries.push({
        time: formatTime(e.timestamp),
        text: `[user] ${e.message}`,
        type: 'user'
      })
    }

    // Add metrics
    for (const m of metrics) {
      entries.push({
        time: formatTime(m.timestamp),
        text: `[${m.source}] ${m.metric}: ${formatValue(m.value)}`,
        type: 'metric'
      })
    }

    // Add activity log
    for (const a of activityLog) {
      entries.push({
        time: formatTime(a.timestamp),
        text: `[${a.step}] ${a.message}`,
        type: 'activity'
      })
    }

    // Sort by timestamp
    return entries.sort((a, b) => a.time.localeCompare(b.time))
  }, [metrics, activityLog, userEvents])

  // Download log as text file
  const handleDownload = () => {
    const logContent = allEntries.map(e => `${e.time} ${e.text}`).join('\n')
    const blob = new Blob([logContent], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analysis-log-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full w-full flex flex-col bg-black/90 rounded border border-zinc-700 font-mono text-[11px]">
      {/* Header */}
      <div className="px-2 py-1 border-b border-zinc-700 text-zinc-400 flex justify-between items-center">
        <span>Log</span>
        <button
          onClick={handleDownload}
          disabled={allEntries.length === 0}
          className="p-1 hover:bg-zinc-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Download log"
        >
          <Download className="h-3 w-3" />
        </button>
      </div>

      {/* Log content */}
      <div
        ref={logRef}
        className="flex-1 overflow-y-auto overflow-x-auto p-2 space-y-0.5"
      >
        {allEntries.length === 0 && !isTyping ? (
          <div className="text-zinc-500">Waiting for input...</div>
        ) : (
          <>
            {allEntries.map((entry, i) => (
              <div key={i} className="text-zinc-300 whitespace-nowrap">
                <span className="text-zinc-500">{entry.time}</span>
                {' '}
                <span className={
                  entry.type === 'metric' ? 'text-green-400' :
                  entry.type === 'user' ? 'text-blue-400' :
                  'text-zinc-300'
                }>
                  {entry.text}
                </span>
              </div>
            ))}
            {/* Live typing indicator */}
            {isTyping && (
              <div className="text-zinc-300 whitespace-nowrap">
                <span className="text-zinc-500">{getCurrentTime()}</span>
                {' '}
                <span className="text-blue-400">[user] Typing...</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-2 py-1 border-t border-zinc-700 text-zinc-500 flex justify-between">
        <span>Step: {currentStep}</span>
        {revisionCount > 0 && <span>Rev #{revisionCount}</span>}
      </div>
    </div>
  )
}

export default MetricsPanel
