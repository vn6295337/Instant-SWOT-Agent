import React from "react"
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
  rawData: MCPRawData
}

// Format numbers for display
function formatValue(value: unknown, type: 'currency' | 'percent' | 'ratio' | 'number' = 'number'): string {
  if (value === null || value === undefined) return '—'

  const num = typeof value === 'number' ? value : parseFloat(String(value))
  if (isNaN(num)) return String(value)

  switch (type) {
    case 'currency':
      if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(1)}T`
      if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(1)}B`
      if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(1)}M`
      return `$${num.toLocaleString()}`
    case 'percent':
      return `${(num * 100).toFixed(1)}%`
    case 'ratio':
      return num.toFixed(2)
    default:
      return num.toFixed(2)
  }
}

// MCP row component
interface MCPRowProps {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
  available: boolean
}

function MCPRow({ icon, label, children, available }: MCPRowProps) {
  return (
    <div className={`flex items-center gap-2 py-1.5 px-3 border-b border-border last:border-b-0 ${!available ? 'opacity-50' : ''}`}>
      <div className="flex items-center gap-2 w-24 shrink-0">
        {icon}
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="flex-1 flex items-center gap-3 overflow-x-auto text-xs">
        {available ? children : <span className="text-muted-foreground italic">Unavailable</span>}
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

// Link item component for news/sentiment
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
      className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 hover:underline whitespace-nowrap max-w-[200px] truncate"
      title={title}
    >
      <span className="truncate">{title}</span>
      <ExternalLink className="h-3 w-3 shrink-0" />
    </a>
  )
}

export function MCPDataPanel({ rawData }: MCPDataPanelProps) {
  const sourcesAvailable = new Set(rawData.sources_available || [])

  const { financials, valuation, volatility, macro, news, sentiment } = rawData

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-3 py-2 bg-muted/50 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">Source Data</h3>
      </div>

      <div className="divide-y divide-border">
        {/* Financials */}
        <MCPRow
          icon={<DollarSign className="h-4 w-4 text-emerald-500" />}
          label="Financials"
          available={sourcesAvailable.has('financials')}
        >
          {financials && (
            <>
              {financials.revenue !== undefined && <DataItem label="Revenue" value={formatValue(financials.revenue, 'currency')} />}
              {financials.gross_margin !== undefined && <DataItem label="Gross Margin" value={formatValue(financials.gross_margin, 'percent')} />}
              {financials.operating_margin !== undefined && <DataItem label="Op Margin" value={formatValue(financials.operating_margin, 'percent')} />}
              {financials.net_margin !== undefined && <DataItem label="Net Margin" value={formatValue(financials.net_margin, 'percent')} />}
              {financials.debt_to_equity !== undefined && <DataItem label="D/E" value={formatValue(financials.debt_to_equity, 'ratio')} />}
              {financials.current_ratio !== undefined && <DataItem label="Current" value={formatValue(financials.current_ratio, 'ratio')} />}
            </>
          )}
        </MCPRow>

        {/* Valuation */}
        <MCPRow
          icon={<TrendingUp className="h-4 w-4 text-blue-500" />}
          label="Valuation"
          available={sourcesAvailable.has('valuation')}
        >
          {valuation && (
            <>
              {valuation.market_cap !== undefined && <DataItem label="Mkt Cap" value={formatValue(valuation.market_cap, 'currency')} />}
              {valuation.pe_ratio !== undefined && <DataItem label="P/E" value={formatValue(valuation.pe_ratio, 'ratio')} />}
              {valuation.ps_ratio !== undefined && <DataItem label="P/S" value={formatValue(valuation.ps_ratio, 'ratio')} />}
              {valuation.pb_ratio !== undefined && <DataItem label="P/B" value={formatValue(valuation.pb_ratio, 'ratio')} />}
              {valuation.ev_ebitda !== undefined && <DataItem label="EV/EBITDA" value={formatValue(valuation.ev_ebitda, 'ratio')} />}
              {valuation.peg_ratio !== undefined && <DataItem label="PEG" value={formatValue(valuation.peg_ratio, 'ratio')} />}
            </>
          )}
        </MCPRow>

        {/* Volatility */}
        <MCPRow
          icon={<Activity className="h-4 w-4 text-yellow-500" />}
          label="Volatility"
          available={sourcesAvailable.has('volatility')}
        >
          {volatility && (
            <>
              {volatility.beta !== undefined && <DataItem label="Beta" value={formatValue(volatility.beta, 'ratio')} />}
              {volatility.vix !== undefined && <DataItem label="VIX" value={formatValue(volatility.vix, 'ratio')} />}
              {volatility.historical_volatility !== undefined && <DataItem label="Hist Vol" value={formatValue(volatility.historical_volatility, 'percent')} />}
              {volatility.implied_volatility !== undefined && <DataItem label="Impl Vol" value={formatValue(volatility.implied_volatility, 'percent')} />}
            </>
          )}
        </MCPRow>

        {/* Macro */}
        <MCPRow
          icon={<Globe className="h-4 w-4 text-purple-500" />}
          label="Macro"
          available={sourcesAvailable.has('macro')}
        >
          {macro && (
            <>
              {macro.gdp_growth !== undefined && <DataItem label="GDP" value={formatValue(macro.gdp_growth, 'percent')} />}
              {macro.interest_rate !== undefined && <DataItem label="Fed Rate" value={formatValue(macro.interest_rate, 'percent')} />}
              {macro.inflation_rate !== undefined && <DataItem label="CPI" value={formatValue(macro.inflation_rate, 'percent')} />}
              {macro.unemployment_rate !== undefined && <DataItem label="Unemp" value={formatValue(macro.unemployment_rate, 'percent')} />}
            </>
          )}
        </MCPRow>

        {/* News */}
        <MCPRow
          icon={<Newspaper className="h-4 w-4 text-orange-500" />}
          label="News"
          available={sourcesAvailable.has('news')}
        >
          {news && news.length > 0 && (
            <>
              {news.slice(0, 4).map((article, i) => (
                <LinkItem
                  key={i}
                  title={article.title}
                  url={article.url}
                />
              ))}
              {news.length > 4 && (
                <span className="text-muted-foreground">+{news.length - 4} more</span>
              )}
            </>
          )}
        </MCPRow>

        {/* Sentiment */}
        <MCPRow
          icon={<MessageSquare className="h-4 w-4 text-pink-500" />}
          label="Sentiment"
          available={sourcesAvailable.has('sentiment')}
        >
          {sentiment && (
            <>
              {sentiment.analyst_rating && <DataItem label="Rating" value={String(sentiment.analyst_rating)} />}
              {sentiment.analyst_target_price !== undefined && <DataItem label="Target" value={formatValue(sentiment.analyst_target_price, 'currency')} />}
              {sentiment.social_sentiment !== undefined && <DataItem label="Social" value={formatValue(sentiment.social_sentiment, 'percent')} />}
              {sentiment.news_sentiment !== undefined && <DataItem label="News Sent" value={formatValue(sentiment.news_sentiment, 'percent')} />}
              {sentiment.insider_sentiment && <DataItem label="Insider" value={String(sentiment.insider_sentiment)} />}
            </>
          )}
        </MCPRow>
      </div>
    </div>
  )
}

export default MCPDataPanel
