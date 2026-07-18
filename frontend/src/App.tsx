import { useState, useEffect, useRef, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Toaster } from "@/components/ui/toaster"
import { TooltipProvider } from "@/components/ui/tooltip"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import {
  startAnalysis,
  getWorkflowStatus,
  getWorkflowResult,
  getWorkflowEventsUrl,
  StockResult,
  WorkflowStatus,
  ActivityLogEntry,
  MCPStatus,
  LLMStatus,
  MetricEntry,
  UserApiKeys,
} from "@/lib/api"
import { AnalysisResponse } from "@/lib/types"
import {
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  BarChart3,
  RefreshCw,
  Play,
  Copy,
  Download,
  Printer,
  Check,
  Pause,
  X,
  Loader2,
  Settings,
  Key,
  ChevronDown,
  ChevronUp,
  Database,
} from "lucide-react"

// Import new components
import { ProcessFlow } from "@/components/ProcessFlow"
import { StockSearch } from "@/components/StockSearch"
import { ActivityLog } from "@/components/ActivityLog"
import { MCPDataPanel } from "@/components/MCPDataPanel"

const queryClient = new QueryClient()

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
)

export default App

const defaultMCPStatus: MCPStatus = {
  fundamentals: 'idle',
  valuation: 'idle',
  volatility: 'idle',
  macro: 'idle',
  news: 'idle',
  sentiment: 'idle',
}

const defaultLLMStatus: LLMStatus = {
  groq: 'idle',
  gemini: 'idle',
  openrouter: 'idle',
}

// Helper to clean markdown formatting (strip asterisks, bold markers)
const cleanMarkdown = (text: string): string => {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')  // Remove **bold**
    .replace(/\*([^*]+)\*/g, '$1')       // Remove *italic*
    .replace(/^\*\s*/gm, '')             // Remove bullet asterisks at line start
    .trim()
}

// Parse structured SWOT line: "[M01] Revenue: $394.3B - Strong market position"
// Returns { ref, metric, insight } or null if line doesn't match pattern
interface SwotRow {
  ref: string
  metric: string
  insight: string
}

const parseSwotLine = (line: string): SwotRow | null => {
  // Clean markdown first
  const cleaned = cleanMarkdown(line)

  // Pattern: [M##] Metric: Value - Insight
  // Use " - " (space-hyphen-space) to avoid matching hyphens in dates like "2024-12-31"
  // Also handle: [M##] Metric: Value | Insight (pipe separator)
  const match = cleaned.match(/^\[?(M\d+)\]?\s*(.+?)\s+[-|]\s+(.+)$/i)
  if (match) {
    return {
      ref: match[1],
      metric: match[2].trim(),
      insight: match[3].trim()
    }
  }

  // Fallback: no ref pattern, just "Metric: Value - Insight"
  const fallback = cleaned.match(/^(.+?)\s+[-|]\s+(.+)$/)
  if (fallback) {
    return {
      ref: '',
      metric: fallback[1].trim(),
      insight: fallback[2].trim()
    }
  }

  // Last resort: just return the cleaned line as insight
  if (cleaned.length > 0) {
    return {
      ref: '',
      metric: '',
      insight: cleaned
    }
  }

  return null
}

const Index = () => {
  const [selectedStock, setSelectedStock] = useState<StockResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showResults, setShowResults] = useState(false)
  const [mainTab, setMainTab] = useState<"flow" | "results">("flow")
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null)
  const [workflowId, setWorkflowId] = useState<string | null>(null)

  // Workflow tracking
  const [currentStep, setCurrentStep] = useState<string>('idle')
  const [completedSteps, setCompletedSteps] = useState<string[]>([])
  const [mcpStatus, setMcpStatus] = useState<MCPStatus>(defaultMCPStatus)
  const [llmStatus, setLlmStatus] = useState<LLMStatus>(defaultLLMStatus)
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>([])
  const [metrics, setMetrics] = useState<MetricEntry[]>([])
  const [revisionCount, setRevisionCount] = useState(0)
  const [score, setScore] = useState(0)
  const [llmProvider, setLlmProvider] = useState<string>('')
  const [cacheHit, setCacheHit] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [isAborted, setIsAborted] = useState(false)
  const [abortReason, setAbortReason] = useState<string>('')
  const [userEvents, setUserEvents] = useState<Array<{timestamp: string; message: string}>>([])

  // User API keys (optional - for when server keys hit rate limits)
  const [userApiKeys, setUserApiKeys] = useState<UserApiKeys>({})
  const [showApiKeySettings, setShowApiKeySettings] = useState(false)

  // Cache dialog state
  const [showCacheDialog, setShowCacheDialog] = useState(false)
  const [pendingCacheWorkflowId, setPendingCacheWorkflowId] = useState<string | null>(null)

  const [copied, setCopied] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Stop whichever status transport is active (SSE stream or polling timer)
  const stopStatusTransport = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }

  // Helper to add user events to log
  const addUserEvent = (message: string) => {
    setUserEvents(prev => [...prev, { timestamp: new Date().toISOString(), message }])
  }

  // Browser Notification helper
  const notify = (title: string, body: string, type: 'success' | 'error' = 'success') => {
    if (Notification.permission === 'granted') {
      new Notification(title, {
        body,
        icon: type === 'success' ? '/favicon.ico' : undefined,
        tag: 'swot-notification', // Prevents duplicate notifications
      })
    }
  }

  // Request notification permission on first stock selection
  const requestNotificationPermission = () => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }

  // Process one status snapshot (shared by the SSE and polling transports)
  const processStatus = async (status: WorkflowStatus, workflowIdToUse: string) => {
        setRevisionCount(status.revision_count)
        setScore(status.score)
        setActivityLog(status.activity_log || [])
        setMetrics(status.metrics || [])
        // Merge MCP status - preserve failed/partial states (they persist for session)
        setMcpStatus(prev => {
          const newStatus = status.mcp_status || defaultMCPStatus
          return {
            fundamentals: prev.fundamentals === 'failed' || prev.fundamentals === 'partial' ? prev.fundamentals : newStatus.fundamentals,
            valuation: prev.valuation === 'failed' || prev.valuation === 'partial' ? prev.valuation : newStatus.valuation,
            volatility: prev.volatility === 'failed' || prev.volatility === 'partial' ? prev.volatility : newStatus.volatility,
            macro: prev.macro === 'failed' || prev.macro === 'partial' ? prev.macro : newStatus.macro,
            news: prev.news === 'failed' || prev.news === 'partial' ? prev.news : newStatus.news,
            sentiment: prev.sentiment === 'failed' || prev.sentiment === 'partial' ? prev.sentiment : newStatus.sentiment,
          }
        })
        // Merge LLM status - preserve failed states (they persist for session)
        setLlmStatus(prev => {
          const newStatus = status.llm_status || defaultLLMStatus
          return {
            groq: prev.groq === 'failed' ? prev.groq : newStatus.groq,
            gemini: prev.gemini === 'failed' ? prev.gemini : newStatus.gemini,
            openrouter: prev.openrouter === 'failed' ? prev.openrouter : newStatus.openrouter,
          }
        })
        if (status.provider_used) setLlmProvider(status.provider_used)

        // Update completed steps - accumulate rather than recalculate to handle loops
        const stepOrder = ['input', 'cache', 'researcher', 'analyzer', 'critic', 'output']
        setCompletedSteps(prev => {
          const newCompleted = new Set(prev)
          const currentIdx = stepOrder.indexOf(status.current_step)

          // Mark all steps before current as completed
          for (let i = 0; i < currentIdx; i++) {
            newCompleted.add(stepOrder[i])
          }

          return Array.from(newCompleted)
        })

        // Only update currentStep for in-progress workflows to prevent output glow flash
        if (status.status !== 'completed') {
          setCurrentStep(status.current_step)
        }

        // Set cacheHit flag for ProcessFlow visualization
        if (status.data_source === 'cache') {
          setCacheHit(true)
        }

        if (status.status === "completed") {
          stopStatusTransport()

          // Check if this was a cache hit - show dialog to let user choose
          if (status.data_source === 'cache') {
            setCacheHit(true)
            setCurrentStep('cache')
            setCompletedSteps(['input', 'cache'])
            setPendingCacheWorkflowId(workflowIdToUse)
            setShowCacheDialog(true)
            // Don't auto-proceed - wait for user choice
            return
          }

          // Normal flow - all steps completed
          // Set completed steps BEFORE the async fetch to prevent output from glowing prematurely
          setCompletedSteps(stepOrder)
          setCurrentStep('completed')
          const result = await getWorkflowResult(workflowIdToUse)
          setAnalysisResult(result)
          setIsLoading(false)
          setShowResults(true)
          setMainTab("results")

          // Notify user that report is ready (works even if tab is in background)
          notify("Analysis complete!", `SWOT report for ${selectedStock?.symbol || 'company'} is ready.`, 'success')
        } else if (status.status === "aborted") {
          stopStatusTransport()
          setIsLoading(false)
          setIsAborted(true)
          setAbortReason(status.error || 'Critical failure - workflow aborted')

          // Notify user of abort (works even if tab is in background)
          notify("Analysis aborted", status.error || "Critical failure - workflow aborted", 'error')
        } else if (status.status === "error") {
          stopStatusTransport()
          setIsLoading(false)
          setHasError(true)

          // Notify user of error (works even if tab is in background)
          notify("Analysis failed", "An error occurred during analysis.", 'error')
        }
  }

  const startIntervalPolling = (workflowIdToUse: string) => {
    pollingRef.current = setInterval(async () => {
      try {
        const status = await getWorkflowStatus(workflowIdToUse)
        await processStatus(status, workflowIdToUse)
      } catch (error) {
        console.error("Polling error:", error)
      }
    }, 700)
  }

  // SSE-first status transport; falls back to 700ms polling if the
  // stream cannot be established or drops mid-workflow
  const startPolling = (workflowIdToUse: string) => {
    stopStatusTransport()
    if (typeof EventSource === 'undefined') {
      startIntervalPolling(workflowIdToUse)
      return
    }
    const es = new EventSource(getWorkflowEventsUrl(workflowIdToUse))
    eventSourceRef.current = es
    es.onmessage = (e) => {
      try {
        processStatus(JSON.parse(e.data) as WorkflowStatus, workflowIdToUse)
      } catch (err) {
        console.error('SSE message error:', err)
      }
    }
    es.onerror = () => {
      // Already stopped (terminal status processed) - nothing to do
      if (eventSourceRef.current !== es) return
      es.close()
      eventSourceRef.current = null
      if (!pollingRef.current) startIntervalPolling(workflowIdToUse)
    }
  }

  // Button state logic
  const buttonState = useMemo(() => {
    if (isAborted) return 'aborted'
    if (hasError) return 'error'
    if (analysisResult && !isLoading) return 'complete'
    if (isPaused) return 'paused'
    if (isLoading) return 'analyzing'
    return 'ready'
  }, [isAborted, hasError, analysisResult, isLoading, isPaused])

  // Pause handler - stop polling
  const handlePause = () => {
    setIsPaused(true)
    stopStatusTransport()
  }

  // Resume handler - restart polling
  const handleResume = () => {
    if (!workflowId) return
    setIsPaused(false)
    startPolling(workflowId)
  }

  // Abort handler - cancel workflow
  const handleAbort = () => {
    stopStatusTransport()
    setIsLoading(false)
    setIsPaused(false)
    setHasError(false)
    setIsAborted(false)
    setAbortReason('')
    setCurrentStep('idle')
    setCompletedSteps([])
    setAnalysisResult(null)
    setShowResults(false)
    setMcpStatus(defaultMCPStatus)
    setLlmStatus(defaultLLMStatus)
  }

  // Cache dialog: Use cached data
  const handleUseCached = async () => {
    if (!pendingCacheWorkflowId) return
    setShowCacheDialog(false)
    addUserEvent('Using cached analysis')

    // Animate cache → output transition
    setCurrentStep('output')
    setTimeout(async () => {
      setCompletedSteps(['input', 'cache', 'output'])
      setCurrentStep('completed')
      // Fetch both result and status (for metrics)
      const [result, status] = await Promise.all([
        getWorkflowResult(pendingCacheWorkflowId),
        getWorkflowStatus(pendingCacheWorkflowId)
      ])
      setAnalysisResult(result)
      setMetrics(status.metrics || [])
      setIsLoading(false)
      setShowResults(true)
      setMainTab("results")
      setPendingCacheWorkflowId(null)
    }, 800)
  }

  // Cache dialog: Run fresh analysis
  const handleRunFresh = async () => {
    if (!selectedStock) return
    setShowCacheDialog(false)
    setPendingCacheWorkflowId(null)
    addUserEvent('Running fresh analysis (cache bypassed)')

    // Reset state for fresh run
    setCurrentStep('input')
    setCompletedSteps([])
    setMcpStatus(defaultMCPStatus)
    setLlmStatus(defaultLLMStatus)
    setActivityLog([])
    setMetrics([])
    setRevisionCount(0)
    setScore(0)
    setCacheHit(false)
    setAnalysisResult(null)

    try {
      const { workflow_id } = await startAnalysis(
        selectedStock.name,
        selectedStock.symbol,
        'Competitive Position',
        true,  // skipCache = true
        userApiKeys
      )
      setWorkflowId(workflow_id)
      setCompletedSteps(['input'])
      setCurrentStep('cache')
      startPolling(workflow_id)
    } catch (error) {
      console.error("Error starting fresh analysis:", error)
      setIsLoading(false)
      setHasError(true)
    }
  }

  // Force dark mode
  useEffect(() => {
    document.documentElement.classList.add("dark")
  }, [])

  // Export functions
  const formatSwotForClipboard = () => {
    if (!analysisResult) return ''
    return `SWOT Analysis: ${analysisResult.company_name}
Quality Score: ${analysisResult.score}/10
Revisions: ${analysisResult.revision_count}

STRENGTHS:
${analysisResult.swot_data.strengths.map(s => `- ${cleanMarkdown(s)}`).join('\n')}

WEAKNESSES:
${analysisResult.swot_data.weaknesses.map(w => `- ${cleanMarkdown(w)}`).join('\n')}

OPPORTUNITIES:
${analysisResult.swot_data.opportunities.map(o => `- ${cleanMarkdown(o)}`).join('\n')}

THREATS:
${analysisResult.swot_data.threats.map(t => `- ${cleanMarkdown(t)}`).join('\n')}

QUALITY EVALUATION:
${analysisResult.critique}

---
Generated by Instant SWOT Agent`
  }

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(formatSwotForClipboard())
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const downloadAsJson = () => {
    if (!analysisResult) return
    const exportData = {
      ...analysisResult,
      exported_at: new Date().toISOString()
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `swot-analysis-${analysisResult.company_name.toLowerCase().replace(/\s+/g, '-')}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleGenerate = async () => {
    if (!selectedStock) return

    addUserEvent(`Analysis started for ${selectedStock.symbol}`)
    setIsLoading(true)
    setShowResults(false)
    setCurrentStep('input')
    setCompletedSteps([])
    setMcpStatus(defaultMCPStatus)
    setLlmStatus(defaultLLMStatus)
    setActivityLog([])
    setMetrics([])
    setRevisionCount(0)
    setScore(0)
    setCacheHit(false)
    setIsPaused(false)
    setHasError(false)
    setIsAborted(false)
    setAbortReason('')
    setAnalysisResult(null)

    try {
      const { workflow_id } = await startAnalysis(
        selectedStock.name,
        selectedStock.symbol,
        'Competitive Position',
        false,  // skipCache = false (check cache first)
        userApiKeys
      )
      setWorkflowId(workflow_id)
      setCompletedSteps(['input'])
      setCurrentStep('cache')
      startPolling(workflow_id)

    } catch (error) {
      console.error("Error starting analysis:", error)
      setIsLoading(false)
      setHasError(true)
    }
  }

  useEffect(() => {
    return () => {
      stopStatusTransport()
    }
  }, [])

  const getScoreColor = (score: number) => {
    if (score >= 7) return "text-emerald-400"
    if (score >= 5) return "text-yellow-400"
    return "text-red-400"
  }

  const getScoreBadge = (score: number) => {
    if (score >= 6)
      return { label: "", variant: "default" as const, icon: CheckCircle }
    return { label: "", variant: "destructive" as const, icon: XCircle }
  }

  const handleStockClear = () => {
    setSelectedStock(null)
    setShowResults(false)
    setAnalysisResult(null)
    setCurrentStep('idle')
    setCompletedSteps([])
    setActivityLog([])
    setMetrics([])
    setUserEvents([])
    setHasError(false)
    setIsAborted(false)
    setAbortReason('')
    setMcpStatus(defaultMCPStatus)
    setLlmStatus(defaultLLMStatus)
  }

  return (
    <Tabs value={mainTab} onValueChange={(v) => setMainTab(v as "flow" | "results")} className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card sticky top-0 z-40">
        <div className="container mx-auto px-4 sm:px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="shrink-0">
              <h1 className="text-lg font-semibold text-foreground">
                Instant SWOT Agent
              </h1>
              <p className="text-xs text-muted-foreground hidden sm:block">
                with self-correcting feedback
              </p>
            </div>
            <div className="flex-1 max-w-xl">
              <StockSearch
                onSelect={(stock) => {
                  setSelectedStock(stock)
                  addUserEvent(`Selected: ${stock.name} (${stock.symbol})`)
                  requestNotificationPermission()
                }}
                selectedStock={selectedStock}
                onClear={handleStockClear}
                disabled={isLoading}
                onSearchChange={setIsSearching}
              />
            </div>
            {/* Dynamic Submit/Control Buttons */}
            <div className="flex items-center gap-2 shrink-0">
              {buttonState === 'ready' && (
                <Button
                  onClick={handleGenerate}
                  disabled={!selectedStock}
                  className="gap-2"
                >
                  <Play className="h-4 w-4" />
                  Submit
                </Button>
              )}

              {buttonState === 'analyzing' && (
                <>
                  <Button onClick={handlePause} className="gap-2 btn-amber btn-amber-pulse">
                    <Pause className="h-4 w-4" />
                    Pause
                  </Button>
                  <Button variant="destructive" onClick={handleAbort} className="gap-2">
                    <X className="h-4 w-4" />
                    Abort
                  </Button>
                </>
              )}

              {buttonState === 'paused' && (
                <>
                  <Button onClick={handleResume} className="gap-2 btn-amber">
                    <Play className="h-4 w-4" />
                    Resume
                  </Button>
                  <Button variant="destructive" onClick={handleAbort} className="gap-2">
                    <X className="h-4 w-4" />
                    Abort
                  </Button>
                </>
              )}

              {buttonState === 'complete' && (
                <Button className="gap-2 btn-green" disabled>
                  <Check className="h-4 w-4" />
                  Complete
                </Button>
              )}

              {buttonState === 'error' && (
                <Button variant="destructive" onClick={handleGenerate} className="gap-2">
                  <X className="h-4 w-4" />
                  Failed - Retry
                </Button>
              )}

              {buttonState === 'aborted' && (
                <Button variant="destructive" onClick={handleStockClear} className="gap-2" title={abortReason}>
                  <AlertTriangle className="h-4 w-4" />
                  Aborted
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Cache Hit Dialog */}
      {showCacheDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5 text-blue-500" />
                Cached Analysis Found
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                A recent analysis for <span className="font-medium text-foreground">{selectedStock?.symbol}</span> was found in cache.
                Would you like to use the cached result or run a fresh analysis?
              </p>
              <div className="flex gap-3">
                <Button onClick={handleUseCached} className="flex-1 gap-2">
                  <Database className="h-4 w-4" />
                  Use Cached
                </Button>
                <Button onClick={handleRunFresh} variant="outline" className="flex-1 gap-2">
                  <RefreshCw className="h-4 w-4" />
                  Run Fresh
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* API Key Settings (Expandable) */}
      <div className="container mx-auto px-4 sm:px-6 pt-2">
        <button
          onClick={() => setShowApiKeySettings(!showApiKeySettings)}
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <Key className="h-3 w-3" />
          <span>API Keys (Optional)</span>
          {showApiKeySettings ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>

        {showApiKeySettings && (
          <Card className="mt-2 p-3">
            <p className="text-xs text-muted-foreground mb-3">
              Provide your own API keys if server keys hit rate limits. Keys are not stored.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Groq</label>
                <input
                  type="password"
                  placeholder="gsk_..."
                  value={userApiKeys.groq || ''}
                  onChange={(e) => setUserApiKeys(prev => ({ ...prev, groq: e.target.value || undefined }))}
                  className="w-full px-2 py-1 text-xs bg-background border rounded focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Gemini</label>
                <input
                  type="password"
                  placeholder="AI..."
                  value={userApiKeys.gemini || ''}
                  onChange={(e) => setUserApiKeys(prev => ({ ...prev, gemini: e.target.value || undefined }))}
                  className="w-full px-2 py-1 text-xs bg-background border rounded focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">OpenRouter</label>
                <input
                  type="password"
                  placeholder="sk-or-..."
                  value={userApiKeys.openrouter || ''}
                  onChange={(e) => setUserApiKeys(prev => ({ ...prev, openrouter: e.target.value || undefined }))}
                  className="w-full px-2 py-1 text-xs bg-background border rounded focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
            </div>
          </Card>
        )}
      </div>

      <main className="container mx-auto px-4 sm:px-6 pt-4 pb-6 space-y-6 overflow-visible">

        {/* Process Flow + Metrics Panel */}
        <div className="flex gap-4">
          <div className="shrink-0">
            <ProcessFlow
              currentStep={currentStep}
              completedSteps={completedSteps}
              mcpStatus={mcpStatus}
              llmStatus={llmStatus}
              llmProvider={llmProvider}
              cacheHit={cacheHit}
              stockSelected={!!selectedStock}
              isSearching={isSearching}
              revisionCount={revisionCount}
              isAborted={isAborted || hasError}
            />
          </div>
          <div className="flex-1 min-w-0 h-[260px]">
            <ActivityLog
              metrics={metrics}
              activityLog={activityLog}
              currentStep={currentStep}
              revisionCount={revisionCount}
              score={score}
              isTyping={isSearching}
              userEvents={userEvents}
            />
          </div>
        </div>

        {/* Results Tab - SWOT cards + metrics */}
        {(isLoading || showResults) && (
          <TabsContent value="results" className="mt-0">
              {analysisResult && (
                <div className="space-y-6 animate-slide-up">
                  {/* Results Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h2 className="text-2xl font-semibold text-foreground">
                        {analysisResult.company_name} ({selectedStock?.symbol})
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        {selectedStock?.exchange}
                      </p>
                      {analysisResult.business_address && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {analysisResult.business_address}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-4">
                      {/* Metrics */}
                      <div className="flex items-center gap-4">
                        <div className="text-center px-4 py-2 bg-card rounded-lg border">
                          <p className="text-xs text-muted-foreground">Score</p>
                          <p className={`text-xl font-bold ${getScoreColor(analysisResult.score)}`}>
                            {analysisResult.score}/10
                          </p>
                        </div>
                        <div className="text-center px-4 py-2 bg-card rounded-lg border">
                          <p className="text-xs text-muted-foreground">Revisions</p>
                          <p className="text-xl font-bold text-foreground">
                            {analysisResult.revision_count}
                          </p>
                        </div>
                      </div>
                      <Badge variant={getScoreBadge(analysisResult.score).variant} className="gap-1.5">
                        {(() => {
                          const BadgeIcon = getScoreBadge(analysisResult.score).icon
                          return <BadgeIcon className="h-4 w-4" />
                        })()}
                        {getScoreBadge(analysisResult.score).label}
                      </Badge>
                    </div>
                  </div>

                  {/* Export Buttons */}
                  <div className="flex flex-wrap gap-2 print:hidden">
                    <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-1.5">
                      <Download className="h-4 w-4" />
                      Download
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-1.5">
                      <Printer className="h-4 w-4" />
                      Print
                    </Button>
                  </div>

                  {/* MCP Source Data */}
                  {metrics.length > 0 && (
                    <MCPDataPanel
                      metrics={metrics}
                      metricReference={analysisResult.metric_reference}
                      rawData={analysisResult.raw_data}
                      companyName={analysisResult.company_name}
                      ticker={selectedStock?.symbol}
                      exchange={selectedStock?.exchange}
                    />
                  )}

                  {/* SWOT Analysis - Tables */}
                  <div className="space-y-6">
                    {/* Strengths Table */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-emerald-500 mb-3 border-b border-emerald-500/30 pb-2">
                        <TrendingUp className="h-5 w-5" />
                        Strengths
                      </h3>
                      <table className="w-full text-sm border-collapse">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-2 px-2 w-12 text-muted-foreground font-medium">Ref</th>
                            <th className="text-left py-2 px-2 w-1/3 text-muted-foreground font-medium">Metric</th>
                            <th className="text-left py-2 px-2 text-muted-foreground font-medium">Insight</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analysisResult.swot_data.strengths.map((item, i) => {
                            const parsed = parseSwotLine(item)
                            if (!parsed) return null
                            return (
                              <tr key={i} className="border-b border-border/50 hover:bg-emerald-500/5">
                                <td className="py-2 px-2 text-emerald-500 font-mono text-xs">{parsed.ref}</td>
                                <td className="py-2 px-2 text-foreground">{parsed.metric}</td>
                                <td className="py-2 px-2 text-muted-foreground">{parsed.insight}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Weaknesses Table */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-red-500 mb-3 border-b border-red-500/30 pb-2">
                        <TrendingDown className="h-5 w-5" />
                        Weaknesses
                      </h3>
                      <table className="w-full text-sm border-collapse">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-2 px-2 w-12 text-muted-foreground font-medium">Ref</th>
                            <th className="text-left py-2 px-2 w-1/3 text-muted-foreground font-medium">Metric</th>
                            <th className="text-left py-2 px-2 text-muted-foreground font-medium">Insight</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analysisResult.swot_data.weaknesses.map((item, i) => {
                            const parsed = parseSwotLine(item)
                            if (!parsed) return null
                            return (
                              <tr key={i} className="border-b border-border/50 hover:bg-red-500/5">
                                <td className="py-2 px-2 text-red-500 font-mono text-xs">{parsed.ref}</td>
                                <td className="py-2 px-2 text-foreground">{parsed.metric}</td>
                                <td className="py-2 px-2 text-muted-foreground">{parsed.insight}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Opportunities Table */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-blue-500 mb-3 border-b border-blue-500/30 pb-2">
                        <Target className="h-5 w-5" />
                        Opportunities
                      </h3>
                      <table className="w-full text-sm border-collapse">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-2 px-2 w-12 text-muted-foreground font-medium">Ref</th>
                            <th className="text-left py-2 px-2 w-1/3 text-muted-foreground font-medium">Metric</th>
                            <th className="text-left py-2 px-2 text-muted-foreground font-medium">Insight</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analysisResult.swot_data.opportunities.map((item, i) => {
                            const parsed = parseSwotLine(item)
                            if (!parsed) return null
                            return (
                              <tr key={i} className="border-b border-border/50 hover:bg-blue-500/5">
                                <td className="py-2 px-2 text-blue-500 font-mono text-xs">{parsed.ref}</td>
                                <td className="py-2 px-2 text-foreground">{parsed.metric}</td>
                                <td className="py-2 px-2 text-muted-foreground">{parsed.insight}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Threats Table */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-yellow-500 mb-3 border-b border-yellow-500/30 pb-2">
                        <AlertTriangle className="h-5 w-5" />
                        Threats
                      </h3>
                      <table className="w-full text-sm border-collapse">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-2 px-2 w-12 text-muted-foreground font-medium">Ref</th>
                            <th className="text-left py-2 px-2 w-1/3 text-muted-foreground font-medium">Metric</th>
                            <th className="text-left py-2 px-2 text-muted-foreground font-medium">Insight</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analysisResult.swot_data.threats.map((item, i) => {
                            const parsed = parseSwotLine(item)
                            if (!parsed) return null
                            return (
                              <tr key={i} className="border-b border-border/50 hover:bg-yellow-500/5">
                                <td className="py-2 px-2 text-yellow-500 font-mono text-xs">{parsed.ref}</td>
                                <td className="py-2 px-2 text-foreground">{parsed.metric}</td>
                                <td className="py-2 px-2 text-muted-foreground">{parsed.insight}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Recommendations (uncited action items separated from the quadrants) */}
                  {analysisResult.recommendations && analysisResult.recommendations.length > 0 && (
                    <div className="mt-6">
                      <h3 className="flex items-center gap-2 text-base font-semibold text-sky-500 mb-3 border-b border-sky-500/30 pb-2">
                        <Target className="h-5 w-5" />
                        Recommendations
                      </h3>
                      <ul className="space-y-2 text-sm text-muted-foreground list-disc pl-6">
                        {analysisResult.recommendations.map((rec, i) => (
                          <li key={i}>{cleanMarkdown(rec)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Data Quality Notes - Hidden for now, will revisit later */}
                </div>
              )}
            </TabsContent>
        )}
      </main>

    </Tabs>
  )
}

const NotFound = () => (
  <div className="min-h-screen bg-background flex flex-col items-center justify-center">
    <div className="text-center space-y-4">
      <h1 className="text-4xl font-bold text-foreground">404</h1>
      <p className="text-xl text-muted-foreground">Page Not Found</p>
      <Button onClick={() => window.location.href = '/'}>Go Home</Button>
    </div>
  </div>
)
