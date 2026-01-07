import React from "react"
import type { MetricEntry } from "@/lib/api"
import type { MCPRawData } from "@/lib/types"
import {
  DollarSign,
  TrendingUp,
  Activity,
  Globe,
  Newspaper,
  MessageSquare,
  ExternalLink
} from "lucide-react"

interface MCPDataPanelProps {
  metrics: MetricEntry[]
  rawData?: MCPRawData
}

// Format numbers for display
function formatValue(value: string | number): string {
  if (value === null || value === undefined) return '—'

  if (typeof value === 'string') return value

  const num = value
  if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(1)}T`
  if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(1)}B`
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(1)}M`
  if (Math.abs(num) < 0.01 && num !== 0) return num.toExponential(2)
  if (Number.isInteger(num)) return num.toLocaleString()
  return num.toFixed(2)
}

// MCP row component
interface MCPRowProps {
  icon: React.ReactNode
  label: string
  color: string
  children: React.ReactNode
}

function MCPRow({ icon, label, color, children }: MCPRowProps) {
  const hasContent = React.Children.toArray(children).length > 0

  return (
    <div className={`flex items-center gap-2 py-1.5 px-3 border-b border-border last:border-b-0 ${!hasContent ? 'opacity-40' : ''}`}>
      <div className={`flex items-center gap-2 w-24 shrink-0 ${color}`}>
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="flex-1 flex items-center gap-4 overflow-x-auto text-xs scrollbar-thin">
        {hasContent ? children : <span className="text-muted-foreground italic">No data</span>}
      </div>
    </div>
  )
}

// Data item component
interface DataItemProps {
  label: string
  value: string
}

function DataItem({ label, value }: DataItemProps) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-muted-foreground">{label}:</span>{' '}
      <span className="text-foreground font-medium">{value}</span>
    </span>
  )
}

// Link item component for news
interface LinkItemProps {
  title: string
  url: string
}

function LinkItem({ title, url }: LinkItemProps) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 hover:underline whitespace-nowrap max-w-[250px]"
      title={title}
    >
      <span className="truncate">{title}</span>
      <ExternalLink className="h-3 w-3 shrink-0" />
    </a>
  )
}

export function MCPDataPanel({ metrics, rawData }: MCPDataPanelProps) {
  // Group metrics by source
  const groupedMetrics = React.useMemo(() => {
    const groups: Record<string, Array<{metric: string, value: string | number}>> = {
      financials: [],
      valuation: [],
      volatility: [],
      macro: [],
      news: [],
      sentiment: []
    }

    for (const m of metrics) {
      const source = m.source.toLowerCase()
      if (source in groups) {
        groups[source].push({ metric: m.metric, value: m.value })
      }
    }

    return groups
  }, [metrics])

  // Extract news articles from raw_data if available
  const newsArticles = React.useMemo(() => {
    if (!rawData) return []

    // Try to get articles from metrics.news.articles
    const newsData = rawData.metrics?.news || rawData.news
    if (newsData && 'articles' in newsData) {
      return (newsData.articles as Array<{title: string, url: string}>).slice(0, 4)
    }

    // Fallback: check if news is an array directly
    if (Array.isArray(rawData.news)) {
      return rawData.news.slice(0, 4)
    }

    return []
  }, [rawData])

  // Check if we have any data at all
  const hasAnyData = metrics.length > 0 || newsArticles.length > 0

  if (!hasAnyData) {
    return null
  }

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-3 py-2 bg-muted/50 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">Source Data</h3>
      </div>

      <div className="divide-y divide-border">
        {/* Financials */}
        <MCPRow
          icon={<DollarSign className="h-4 w-4" />}
          label="Financials"
          color="text-emerald-500"
        >
          {groupedMetrics.financials.map((m, i) => (
            <DataItem key={i} label={m.metric} value={formatValue(m.value)} />
          ))}
        </MCPRow>

        {/* Valuation */}
        <MCPRow
          icon={<TrendingUp className="h-4 w-4" />}
          label="Valuation"
          color="text-blue-500"
        >
          {groupedMetrics.valuation.map((m, i) => (
            <DataItem key={i} label={m.metric} value={formatValue(m.value)} />
          ))}
        </MCPRow>

        {/* Volatility */}
        <MCPRow
          icon={<Activity className="h-4 w-4" />}
          label="Volatility"
          color="text-yellow-500"
        >
          {groupedMetrics.volatility.map((m, i) => (
            <DataItem key={i} label={m.metric} value={formatValue(m.value)} />
          ))}
        </MCPRow>

        {/* Macro */}
        <MCPRow
          icon={<Globe className="h-4 w-4" />}
          label="Macro"
          color="text-purple-500"
        >
          {groupedMetrics.macro.map((m, i) => (
            <DataItem key={i} label={m.metric} value={formatValue(m.value)} />
          ))}
        </MCPRow>

        {/* News */}
        <MCPRow
          icon={<Newspaper className="h-4 w-4" />}
          label="News"
          color="text-orange-500"
        >
          {newsArticles.length > 0 ? (
            newsArticles.map((article, i) => (
              <LinkItem key={i} title={article.title} url={article.url} />
            ))
          ) : groupedMetrics.news.length > 0 ? (
            groupedMetrics.news.map((m, i) => (
              <DataItem key={i} label={m.metric} value={formatValue(m.value)} />
            ))
          ) : null}
        </MCPRow>

        {/* Sentiment */}
        <MCPRow
          icon={<MessageSquare className="h-4 w-4" />}
          label="Sentiment"
          color="text-pink-500"
        >
          {groupedMetrics.sentiment.map((m, i) => (
            <DataItem key={i} label={m.metric} value={formatValue(m.value)} />
          ))}
        </MCPRow>
      </div>
    </div>
  )
}

export default MCPDataPanel
