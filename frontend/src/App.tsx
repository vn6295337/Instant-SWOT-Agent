import { useState, useEffect, useRef, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Toaster } from "@/components/ui/toaster"
import { Toaster as Sonner } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import {
  startAnalysis,
  getWorkflowStatus,
  getWorkflowResult,
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
  AlertCircle,
  BarChart3,
  RefreshCw,
  Zap,
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
      <Sonner />
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

  // Helper to add user events to log
  const addUserEvent = (message: string) => {
    setUserEvents(prev => [...prev, { timestamp: new Date().toISOString(), message }])
  }

  // Extracted polling logic to avoid duplication
  const startPolling = (workflowIdToUse: string) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
    }

    pollingRef.current = setInterval(async () => {
      try {
        const status = await getWorkflowStatus(workflowIdToUse)
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
        const stepOrder = ['input', 'cache', 'researcher', 'analyzer', 'critic', 'editor', 'output']
        setCompletedSteps(prev => {
          const newCompleted = new Set(prev)
          const currentIdx = stepOrder.indexOf(status.current_step)

          // Mark all steps before current as completed
          for (let i = 0; i < currentIdx; i++) {
            newCompleted.add(stepOrder[i])
          }

          // Handle Critic ↔ Editor loop: keep editor completed when looping back to critic
          if (status.current_step === 'critic' && status.revision_count > 0) {
            newCompleted.add('editor')
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
          clearInterval(pollingRef.current!)
          pollingRef.current = null

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
          // Only mark 'editor' as completed if revisions actually occurred
          const finalSteps = status.revision_count > 0
            ? stepOrder
            : stepOrder.filter(s => s !== 'editor')
          setCompletedSteps(finalSteps)
          setCurrentStep('completed')
          const result = await getWorkflowResult(workflowIdToUse)
          setAnalysisResult(result)
          setIsLoading(false)
          setShowResults(true)
          setMainTab("results")
        } else if (status.status === "aborted") {
          clearInterval(pollingRef.current!)
          pollingRef.current = null
          setIsLoading(false)
          setIsAborted(true)
          setAbortReason(status.error || 'Critical failure - workflow aborted')
        } else if (status.status === "error") {
          clearInterval(pollingRef.current!)
          pollingRef.current = null
          setIsLoading(false)
          setHasError(true)
        }
      } catch (error) {
        console.error("Polling error:", error)
      }
    }, 700)
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
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  // Resume handler - restart polling
  const handleResume = () => {
    if (!workflowId) return
    setIsPaused(false)
    startPolling(workflowId)
  }

  // Abort handler - cancel workflow
  const handleAbort = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
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
      const result = await getWorkflowResult(pendingCacheWorkflowId)
      setAnalysisResult(result)
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
${analysisResult.swot_data.strengths.map(s => `- ${s}`).join('\n')}

WEAKNESSES:
${analysisResult.swot_data.weaknesses.map(w => `- ${w}`).join('\n')}

OPPORTUNITIES:
${analysisResult.swot_data.opportunities.map(o => `- ${o}`).join('\n')}

THREATS:
${analysisResult.swot_data.threats.map(t => `- ${t}`).join('\n')}

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
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])

  const getScoreColor = (score: number) => {
    if (score >= 7) return "text-emerald-400"
    if (score >= 5) return "text-yellow-400"
    return "text-red-400"
  }

  const getScoreBadge = (score: number) => {
    if (score >= 7)
      return { label: "Board-ready", variant: "default" as const, icon: CheckCircle }
    if (score >= 5)
      return { label: "Acceptable", variant: "secondary" as const, icon: AlertCircle }
    return { label: "Needs Review", variant: "destructive" as const, icon: XCircle }
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
                      rawData={analysisResult.raw_data}
                      companyName={analysisResult.company_name}
                      ticker={selectedStock?.symbol}
                      exchange={selectedStock?.exchange}
                    />
                  )}

                  {/* SWOT Analysis */}
                  <div className="space-y-6">
                    {/* Strengths */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-emerald-500 mb-3 border-b border-emerald-500/30 pb-2">
                        <TrendingUp className="h-5 w-5" />
                        Strengths
                      </h3>
                      <ul className="space-y-2 pl-1">
                        {analysisResult.swot_data.strengths.map((item, i) => (
                          <li key={i} className="flex gap-2 text-sm text-foreground">
                            <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Weaknesses */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-red-500 mb-3 border-b border-red-500/30 pb-2">
                        <TrendingDown className="h-5 w-5" />
                        Weaknesses
                      </h3>
                      <ul className="space-y-2 pl-1">
                        {analysisResult.swot_data.weaknesses.map((item, i) => (
                          <li key={i} className="flex gap-2 text-sm text-foreground">
                            <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Opportunities */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-blue-500 mb-3 border-b border-blue-500/30 pb-2">
                        <Target className="h-5 w-5" />
                        Opportunities
                      </h3>
                      <ul className="space-y-2 pl-1">
                        {analysisResult.swot_data.opportunities.map((item, i) => (
                          <li key={i} className="flex gap-2 text-sm text-foreground">
                            <Zap className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Threats */}
                    <div>
                      <h3 className="flex items-center gap-2 text-base font-semibold text-yellow-500 mb-3 border-b border-yellow-500/30 pb-2">
                        <AlertTriangle className="h-5 w-5" />
                        Threats
                      </h3>
                      <ul className="space-y-2 pl-1">
                        {analysisResult.swot_data.threats.map((item, i) => (
                          <li key={i} className="flex gap-2 text-sm text-foreground">
                            <AlertCircle className="h-4 w-4 text-yellow-500 shrink-0 mt-0.5" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Critic Evaluation */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base flex items-center gap-2">
                        <Target className="h-4 w-4" />
                        Quality Evaluation
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {analysisResult.critique}
                      </p>
                    </CardContent>
                  </Card>
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
