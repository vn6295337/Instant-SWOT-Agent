import React from "react"
import type { MetricEntry, MCPStatus } from "@/lib/api"
import type { MCPRawData } from "@/lib/types"
import {
  DollarSign,
  TrendingUp,
  Activity,
  Globe,
  Newspaper,
  MessageSquare,
  ExternalLink,
  Building2,
  MapPin,
  Briefcase,
  Database
} from "lucide-react"

interface MCPDataPanelProps {
  metrics: MetricEntry[]
  rawData?: MCPRawData
  mcpStatus?: MCPStatus
  companyName?: string
  ticker?: string
  exchange?: string
  cik?: string
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

// Format fiscal period label (e.g., "FY 2023" or "Q3 2024")
function formatFiscalPeriod(form?: string, fiscalYear?: number, endDate?: string): string | null {
  if (!fiscalYear) return null

  if (form === '10-K') {
    return `FY ${fiscalYear}`
  } else if (form === '10-Q' && endDate) {
    try {
      // Parse quarter from end date (YYYY-MM-DD)
      const month = parseInt(endDate.split('-')[1], 10)
      const quarter = Math.ceil(month / 3)
      return `Q${quarter} ${fiscalYear}`
    } catch {
      return `FY ${fiscalYear}`
    }
  }
  return `FY ${fiscalYear}`
}

// MCP row component
interface MCPRowProps {
  icon: React.ReactNode
  label: string
  color: string
  children: React.ReactNode
  status?: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
}

function MCPRow({ icon, label, color, children, status }: MCPRowProps) {
  const hasContent = React.Children.toArray(children).length > 0
  const isFailed = status === 'failed'
  const isPartial = status === 'partial'

  // Determine what to show when no content
  const getEmptyMessage = () => {
    if (isFailed) return 'API unavailable'
    if (isPartial) return 'Partial data'
    return 'No data'
  }

  return (
    <div className={`flex items-center gap-2 py-1.5 px-3 border-b border-border last:border-b-0 ${!hasContent && !isFailed ? 'opacity-40' : ''}`}>
      <div className={`flex items-center gap-2 w-28 shrink-0 ${isFailed ? 'text-red-400' : isPartial ? 'text-amber-400' : color}`}>
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="flex-1 flex items-center gap-4 overflow-x-auto text-xs scrollbar-thin">
        {hasContent ? children : (
          <span className={`italic ${isFailed ? 'text-red-400' : isPartial ? 'text-amber-400' : 'text-muted-foreground'}`}>
            {getEmptyMessage()}
          </span>
        )}
      </div>
    </div>
  )
}

// Data item component with optional fiscal period
interface DataItemProps {
  label: string
  value: string
  fiscalPeriod?: string | null  // e.g., "FY 2023" or "Q3 2024"
  endDate?: string              // For tooltip: "2023-09-30"
}

function DataItem({ label, value, fiscalPeriod, endDate }: DataItemProps) {
  return (
    <span className="whitespace-nowrap group relative">
      <span className="text-muted-foreground">{label}:</span>{' '}
      <span className="text-foreground font-medium">{value}</span>
      {fiscalPeriod && (
        <span className="text-xs text-muted-foreground ml-1">({fiscalPeriod})</span>
      )}
      {/* Hover tooltip for full period details */}
      {endDate && (
        <span className="hidden group-hover:block absolute bottom-full left-0 mb-1 bg-popover border border-border rounded px-2 py-1 text-xs shadow-lg z-10 whitespace-nowrap">
          Period ending: {endDate}
        </span>
      )}
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

export function MCPDataPanel({ metrics, rawData, mcpStatus, companyName, ticker, exchange, cik }: MCPDataPanelProps) {
  // Group metrics by source, including temporal data
  const groupedMetrics = React.useMemo(() => {
    const groups: Record<string, Array<{
      metric: string
      value: string | number
      fiscalPeriod?: string | null
      endDate?: string
    }>> = {
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
        // Format fiscal period if temporal data is available
        const fiscalPeriod = formatFiscalPeriod(m.form, m.fiscal_year, m.end_date)
        groups[source].push({
          metric: m.metric,
          value: m.value,
          fiscalPeriod,
          endDate: m.end_date
        })
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

  // Extract company profile info from raw_data if available
  const companyProfile = React.useMemo(() => {
    if (!rawData) return null

    // Try to get profile from valuation or company_info
    const profile = rawData.metrics?.valuation?.profile || rawData.company_info || {}
    return {
      sector: profile.sector || profile.industry || null,
      hqLocation: profile.city && profile.state
        ? `${profile.city}, ${profile.state}${profile.country ? `, ${profile.country}` : ''}`
        : profile.address || profile.location || null,
      employees: profile.fullTimeEmployees || profile.employees || null,
    }
  }, [rawData])

  // Check if we have any data at all
  const hasAnyData = metrics.length > 0 || newsArticles.length > 0

  if (!hasAnyData) {
    return null
  }

  // Data sources with expanded names
  const dataSources = [
    { abbr: 'SEC', full: 'Securities and Exchange Commission (SEC) EDGAR' },
    { abbr: 'FRED', full: 'Federal Reserve Economic Data (FRED)' },
    { abbr: 'Yahoo', full: 'Yahoo Finance' },
    { abbr: 'Tavily', full: 'Tavily News API' },
    { abbr: 'Finnhub', full: 'Finnhub Market Data' },
  ]

  return (
    <div className="space-y-4">
      {/* Company Details */}
      {(companyName || ticker) && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-3 py-2 bg-muted/50 border-b border-border">
            <h3 className="text-sm font-medium text-foreground">Company Profile</h3>
          </div>
          <div className="p-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {companyName && (
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{companyName}</span>
                {ticker && <span className="text-muted-foreground">({ticker})</span>}
              </div>
            )}
            {(exchange || cik) && (
              <div className="flex items-center gap-2 text-muted-foreground">
                {exchange && <span>{exchange}</span>}
                {exchange && cik && <span>•</span>}
                {cik && <span>CIK: {cik}</span>}
              </div>
            )}
            {companyProfile?.sector && (
              <div className="flex items-center gap-2">
                <Briefcase className="h-4 w-4 text-muted-foreground" />
                <span>{companyProfile.sector}</span>
              </div>
            )}
            {companyProfile?.hqLocation && (
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-muted-foreground" />
                <span>{companyProfile.hqLocation}</span>
              </div>
            )}
            {companyProfile?.employees && (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Employees:</span>
                <span>{Number(companyProfile.employees).toLocaleString()}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Key Data */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-3 py-2 bg-muted/50 border-b border-border">
          <h3 className="text-sm font-medium text-foreground">Key Data</h3>
        </div>

        <div className="divide-y divide-border">
        {/* Financials - with fiscal period labels */}
        <MCPRow
          icon={<DollarSign className="h-4 w-4" />}
          label="Financials"
          color="text-emerald-500"
          status={mcpStatus?.financials}
        >
          {groupedMetrics.financials.map((m, i) => (
            <DataItem
              key={i}
              label={m.metric}
              value={formatValue(m.value)}
              fiscalPeriod={m.fiscalPeriod}
              endDate={m.endDate}
            />
          ))}
        </MCPRow>

        {/* Valuation */}
        <MCPRow
          icon={<TrendingUp className="h-4 w-4" />}
          label="Valuation"
          color="text-blue-500"
          status={mcpStatus?.valuation}
        >
          {groupedMetrics.valuation.map((m, i) => (
            <DataItem
              key={i}
              label={m.metric}
              value={formatValue(m.value)}
              fiscalPeriod={m.fiscalPeriod}
              endDate={m.endDate}
            />
          ))}
        </MCPRow>

        {/* Volatility */}
        <MCPRow
          icon={<Activity className="h-4 w-4" />}
          label="Volatility"
          color="text-yellow-500"
          status={mcpStatus?.volatility}
        >
          {groupedMetrics.volatility.map((m, i) => (
            <DataItem
              key={i}
              label={m.metric}
              value={formatValue(m.value)}
              fiscalPeriod={m.fiscalPeriod}
              endDate={m.endDate}
            />
          ))}
        </MCPRow>

        {/* Macro (US) */}
        <MCPRow
          icon={<Globe className="h-4 w-4" />}
          label="Macro (US)"
          color="text-purple-500"
          status={mcpStatus?.macro}
        >
          {groupedMetrics.macro.map((m, i) => (
            <DataItem
              key={i}
              label={m.metric}
              value={formatValue(m.value)}
              fiscalPeriod={m.fiscalPeriod}
              endDate={m.endDate}
            />
          ))}
        </MCPRow>

        {/* News */}
        <MCPRow
          icon={<Newspaper className="h-4 w-4" />}
          label="News"
          color="text-orange-500"
          status={mcpStatus?.news}
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
          status={mcpStatus?.sentiment}
        >
          {groupedMetrics.sentiment.map((m, i) => (
            <DataItem
              key={i}
              label={m.metric}
              value={formatValue(m.value)}
              fiscalPeriod={m.fiscalPeriod}
              endDate={m.endDate}
            />
          ))}
        </MCPRow>
        </div>
      </div>

      {/* Data Sources */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-3 py-2 bg-muted/50 border-b border-border">
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <Database className="h-4 w-4" />
            Data Sources
          </h3>
        </div>
        <div className="p-3">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {dataSources.map((source, i) => (
              <span key={i} title={source.full}>{source.abbr}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MCPDataPanel
