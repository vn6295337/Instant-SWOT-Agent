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
} from "lucide-react"

// Import new components
import { ProcessFlow } from "@/components/ProcessFlow"
import { ActivityLog } from "@/components/ActivityLog"
import { StockSearch } from "@/components/StockSearch"
import { MetricsPanel } from "@/components/MetricsPanel"

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
  financials: 'idle',
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
            financials: prev.financials === 'failed' || prev.financials === 'partial' ? prev.financials : newStatus.financials,
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

          // Check if this was a cache hit
          if (status.data_source === 'cache') {
            // Cache hit flow - only animate cache and output
            setCacheHit(true)
            setCurrentStep('cache')
            setCompletedSteps(['input'])

            setTimeout(() => {
              setCompletedSteps(['input', 'cache'])
              setCurrentStep('output')
            }, 800)

            setTimeout(async () => {
              setCompletedSteps(['input', 'cache', 'output'])
              setCurrentStep('completed')
              const result = await getWorkflowResult(workflowIdToUse)
              setAnalysisResult(result)
              setIsLoading(false)
              setShowResults(true)
              setMainTab("results")
            }, 1600)
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
        'Competitive Position'
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
            <MetricsPanel
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

        {/* Flow Tab - Activity Log during loading */}
        {(isLoading || showResults) && (
          <TabsContent value="flow" className="space-y-6 mt-0">
            {isLoading && <ActivityLog entries={activityLog} />}
          </TabsContent>
        )}

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
                    <Button variant="outline" size="sm" onClick={copyToClipboard} className="gap-1.5">
                      {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
                      {copied ? "Copied!" : "Copy"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={downloadAsJson} className="gap-1.5">
                      <Download className="h-4 w-4" />
                      Export JSON
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-1.5">
                      <Printer className="h-4 w-4" />
                      Print
                    </Button>
                  </div>

                  {/* SWOT Cards */}
                  <div className="grid gap-4 md:grid-cols-2">
                    {/* Strengths Card */}
                    <Card className="border-l-4 border-l-emerald-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base text-emerald-500">
                          <TrendingUp className="h-5 w-5" />
                          Strengths
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ul className="space-y-2">
                          {analysisResult.swot_data.strengths.map((item, i) => (
                            <li key={i} className="flex gap-2 text-sm text-foreground">
                              <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>

                    {/* Weaknesses Card */}
                    <Card className="border-l-4 border-l-red-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base text-red-500">
                          <TrendingDown className="h-5 w-5" />
                          Weaknesses
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ul className="space-y-2">
                          {analysisResult.swot_data.weaknesses.map((item, i) => (
                            <li key={i} className="flex gap-2 text-sm text-foreground">
                              <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>

                    {/* Opportunities Card */}
                    <Card className="border-l-4 border-l-blue-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base text-blue-500">
                          <Target className="h-5 w-5" />
                          Opportunities
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ul className="space-y-2">
                          {analysisResult.swot_data.opportunities.map((item, i) => (
                            <li key={i} className="flex gap-2 text-sm text-foreground">
                              <Zap className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>

                    {/* Threats Card */}
                    <Card className="border-l-4 border-l-yellow-500">
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base text-yellow-500">
                          <AlertTriangle className="h-5 w-5" />
                          Threats
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ul className="space-y-2">
                          {analysisResult.swot_data.threats.map((item, i) => (
                            <li key={i} className="flex gap-2 text-sm text-foreground">
                              <AlertCircle className="h-4 w-4 text-yellow-500 shrink-0 mt-0.5" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>
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
