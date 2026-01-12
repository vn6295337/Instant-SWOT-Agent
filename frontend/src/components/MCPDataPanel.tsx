import React from "react"
import type { MetricEntry } from "@/lib/api"
import type { MCPRawData } from "@/lib/types"
import {
  ExternalLink,
  Building2,
  MapPin,
  Briefcase
} from "lucide-react"

interface MCPDataPanelProps {
  metrics: MetricEntry[]
  rawData?: MCPRawData
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

// Infer data source from category and metric
function inferDataSource(category: string, metric: string, form?: string): string {
  const lowerMetric = metric.toLowerCase()

  if (category === 'fundamentals') {
    return form ? 'SEC EDGAR' : 'Yahoo Finance'
  }
  if (category === 'valuation') return 'Yahoo Finance'
  if (category === 'volatility') {
    if (['vix', 'vxn'].includes(lowerMetric)) return 'FRED'
    if (['beta', 'historical_volatility'].includes(lowerMetric)) return 'Calculated (Yahoo Finance)'
    return 'Market Average'
  }
  if (category === 'macro') {
    if (lowerMetric === 'gdp_growth') return 'BEA'
    if (lowerMetric === 'interest_rate') return 'FRED'
    return 'BLS'
  }
  return category
}

// Infer data type from form and metric
function inferDataType(form?: string, metric?: string): string {
  if (form === '10-K') return 'FY'
  if (form === '10-Q') return 'Q'

  const lowerMetric = (metric || '').toLowerCase()
  if (['vix', 'vxn'].includes(lowerMetric)) return 'Daily'
  if (['gdp_growth'].includes(lowerMetric)) return 'Quarterly'
  if (['interest_rate', 'cpi_inflation', 'unemployment'].includes(lowerMetric)) return 'Monthly'
  if (lowerMetric === 'beta') return '1Y'
  if (lowerMetric === 'historical_volatility') return '30D'
  if (lowerMetric === 'implied_volatility') return 'Forward'

  return 'TTM'
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

export function MCPDataPanel({ metrics, rawData, companyName, ticker, exchange, cik }: MCPDataPanelProps) {
  // Group metrics by source, including temporal data
  const groupedMetrics = React.useMemo(() => {
    const groups: Record<string, Array<{
      metric: string
      value: string | number
      fiscalPeriod?: string | null
      endDate?: string
      form?: string
    }>> = {
      fundamentals: [],
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
          endDate: m.end_date,
          form: m.form
        })
      }
    }

    return groups
  }, [metrics])

  // Build quantitative rows for table display
  const quantitativeRows = React.useMemo(() => {
    const categories = ['fundamentals', 'valuation', 'volatility', 'macro']
    const rows: Array<{
      metric: string
      value: string
      dataType: string
      asOf: string
      source: string
      category: string
    }> = []

    for (const cat of categories) {
      for (const m of groupedMetrics[cat] || []) {
        rows.push({
          metric: m.metric,
          value: formatValue(m.value),
          dataType: inferDataType(m.form, m.metric),
          asOf: m.endDate || '-',
          source: inferDataSource(cat, m.metric, m.form),
          category: cat.charAt(0).toUpperCase() + cat.slice(1)
        })
      }
    }
    return rows
  }, [groupedMetrics])

  // Extract news articles from raw_data if available
  // Actual structure: rawData.metrics.news.items[]
  const newsArticles = React.useMemo(() => {
    if (!rawData) return []

    const articles: Array<{
      title: string
      url: string
      date?: string
      source?: string
    }> = []

    // Navigate to metrics.news.items - the actual structure from Research Service
    const metricsObj = rawData.metrics as Record<string, unknown> | undefined
    const newsData = metricsObj?.news as Record<string, unknown> | undefined

    if (newsData) {
      // Get items array (flat list with source field)
      const items = newsData.items as Array<Record<string, unknown>> | undefined
      if (items && Array.isArray(items) && items.length > 0) {
        for (const a of items) {
          articles.push({
            title: String(a.title || a.content || 'News article'),
            url: String(a.url || '#'),
            date: a.datetime ? String(a.datetime) : undefined,
            source: a.source ? String(a.source) : 'Tavily'
          })
        }
      }
    }

    // Fallback: check rawData.news directly (legacy format)
    if (articles.length === 0 && rawData.news && Array.isArray(rawData.news)) {
      for (const a of rawData.news.slice(0, 10)) {
        articles.push({
          title: a.title || 'News article',
          url: a.url || '#',
          date: a.published_date,
          source: a.source || 'Tavily'
        })
      }
    }

    return articles
  }, [rawData])

  // Extract sentiment items (individual news/posts from Finnhub and Reddit)
  // Actual structure: rawData.metrics.sentiment.items[] with source field for filtering
  const sentimentItems = React.useMemo(() => {
    if (!rawData) return []

    const results: Array<{
      title: string
      url: string
      date?: string
      source: string
      subreddit?: string
    }> = []

    // Navigate to metrics.sentiment.items - flat array with source field
    const metricsObj = rawData.metrics as Record<string, unknown> | undefined
    const sentimentData = metricsObj?.sentiment as Record<string, unknown> | undefined

    if (!sentimentData) return []

    const items = sentimentData.items as Array<Record<string, unknown>> | undefined
    if (!items || !Array.isArray(items)) return []

    for (const item of items) {
      const source = String(item.source || 'Unknown')
      results.push({
        title: String(item.title || item.content || `${source} item`),
        url: String(item.url || '#'),
        date: item.datetime ? String(item.datetime) : undefined,
        source,
        subreddit: item.subreddit ? String(item.subreddit) : undefined
      })
    }

    return results
  }, [rawData])

  // Build qualitative rows for table display (news + sentiment)
  const qualitativeRows = React.useMemo(() => {
    const rows: Array<{
      title: string
      date: string
      source: string
      subreddit: string
      url: string
      category: string
    }> = []

    // News articles
    for (const article of newsArticles) {
      rows.push({
        title: article.title,
        date: article.date || '-',
        source: article.source || 'Tavily',
        subreddit: '-',
        url: article.url,
        category: 'News'
      })
    }

    // Sentiment items
    for (const item of sentimentItems) {
      rows.push({
        title: item.title,
        date: item.date || '-',
        source: item.source,
        subreddit: item.subreddit ? `r/${item.subreddit}` : '-',
        url: item.url,
        category: 'Sentiment'
      })
    }

    return rows
  }, [newsArticles, sentimentItems])

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

      {/* Quantitative Data Table */}
      {quantitativeRows.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden w-fit">
          <div className="px-4 py-2 bg-muted/50 border-b border-border">
            <h3 className="text-sm font-medium text-foreground">Quantitative Data</h3>
          </div>
          <div className="overflow-x-auto p-2">
            <table className="text-xs">
              <thead className="bg-muted/30">
                <tr>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">S/N</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Metric</th>
                  <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">Value</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Data Type</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">As Of</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Source</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {quantitativeRows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-muted/20">
                    <td className="px-3 py-1.5 text-muted-foreground">{idx + 1}</td>
                    <td className="px-3 py-1.5">{row.metric}</td>
                    <td className="px-3 py-1.5 text-right font-medium">{row.value}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{row.dataType}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{row.asOf}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{row.source}</td>
                    <td className="px-3 py-1.5">{row.category}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Qualitative Data Table */}
      {qualitativeRows.length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden w-fit">
          <div className="px-4 py-2 bg-muted/50 border-b border-border">
            <h3 className="text-sm font-medium text-foreground">Qualitative Data</h3>
          </div>
          <div className="overflow-x-auto p-2">
            <table className="text-xs">
              <thead className="bg-muted/30">
                <tr>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">S/N</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Title</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Date</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Source</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Subreddit</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">URL</th>
                  <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {qualitativeRows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-muted/20">
                    <td className="px-3 py-1.5 text-muted-foreground">{idx + 1}</td>
                    <td className="px-3 py-1.5 max-w-[250px] truncate" title={row.title}>{row.title}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{row.date}</td>
                    <td className="px-3 py-1.5">{row.source}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{row.subreddit}</td>
                    <td className="px-3 py-1.5">
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 hover:underline inline-flex items-center gap-1"
                      >
                        Link
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </td>
                    <td className="px-3 py-1.5">{row.category}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default MCPDataPanel
