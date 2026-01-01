import React, { useMemo } from "react"
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
  Loader2,
  Network,
  GitBranch,
  TrendingUp,
  DollarSign,
  BarChart3,
  Globe,
  Newspaper,
  Heart,
} from "lucide-react"
import type { MCPStatus, LLMStatus } from "@/lib/api"

// === TYPES ===

type NodeStatus = 'idle' | 'executing' | 'completed' | 'failed' | 'skipped'
type CacheState = 'idle' | 'hit' | 'miss' | 'checking'

interface ProcessFlowProps {
  currentStep: string
  completedSteps: string[]
  mcpStatus: MCPStatus
  llmStatus?: LLMStatus
  llmProvider?: string
  cacheHit?: boolean
  stockSelected?: boolean
  isSearching?: boolean
  revisionCount?: number
  isAborted?: boolean
}

// === CONSTANTS ===

const NODE_SIZE = 44
const ICON_SIZE = 24
const MCP_SIZE = 36
const MCP_ICON_SIZE = 20
const LLM_WIDTH = 64
const LLM_HEIGHT = 24

const GAP = 72
const CONNECTOR_PAD = 2
const GROUP_PAD = 4

// ADJUSTED VALUES FOR TIGHT FIT
const ROW_GAP = 68            // Slight reduction to tighten vertical flow
const ROW1_Y = 48             // Increased for labels above containers
const ROW2_Y = ROW1_Y + ROW_GAP
const ROW3_Y = ROW2_Y + ROW_GAP
// SVG dimensions
const SVG_HEIGHT = 218        // Exact content height - scales to fill container
const NODE_COUNT = 7
const FLOW_WIDTH = GAP * (NODE_COUNT - 1) + NODE_SIZE
const SVG_WIDTH = FLOW_WIDTH  // Match content width exactly
const FLOW_START_X = NODE_SIZE / 2  // Left-aligned with half-node margin

const NODES = {
  input: { x: FLOW_START_X, y: ROW1_Y },
  cache: { x: FLOW_START_X + GAP, y: ROW1_Y },
  a2a: { x: FLOW_START_X + GAP * 2, y: ROW1_Y },
  analyzer: { x: FLOW_START_X + GAP * 3, y: ROW1_Y },
  critic: { x: FLOW_START_X + GAP * 4, y: ROW1_Y },
  editor: { x: FLOW_START_X + GAP * 5, y: ROW1_Y },
  output: { x: FLOW_START_X + GAP * 6, y: ROW1_Y },
  exchange: { x: FLOW_START_X, y: ROW2_Y },
  researcher: { x: FLOW_START_X + GAP * 2, y: ROW3_Y },
}

const MCP_START_X = NODES.researcher.x + NODE_SIZE / 2 + 40
const MCP_GAP = 38
const MCP_SERVERS = [
  { id: 'financials', label: 'Financials', icon: TrendingUp, x: MCP_START_X },
  { id: 'valuation', label: 'Valuation', icon: DollarSign, x: MCP_START_X + MCP_GAP },
  { id: 'volatility', label: 'Volatility', icon: BarChart3, x: MCP_START_X + MCP_GAP * 2 },
  { id: 'macro', label: 'Macro', icon: Globe, x: MCP_START_X + MCP_GAP * 3 },
  { id: 'news', label: 'News', icon: Newspaper, x: MCP_START_X + MCP_GAP * 4 },
  { id: 'sentiment', label: 'Sentiment', icon: Heart, x: MCP_START_X + MCP_GAP * 5 },
]

const AGENTS_CENTER_X = (NODES.analyzer.x + NODES.editor.x) / 2
const LLM_GAP = 68  // LLM_WIDTH (64) + 4px spacing
const LLM_PROVIDERS = [
  { id: 'groq', name: 'Groq', x: AGENTS_CENTER_X - LLM_GAP },
  { id: 'gemini', name: 'Gemini', x: AGENTS_CENTER_X },
  { id: 'openrouter', name: 'OpenRouter', x: AGENTS_CENTER_X + LLM_GAP },
]

const AGENTS_GROUP = {
  x: NODES.analyzer.x - NODE_SIZE / 2 - GROUP_PAD,
  y: ROW1_Y - NODE_SIZE / 2 - GROUP_PAD,
  width: NODES.editor.x - NODES.analyzer.x + NODE_SIZE + GROUP_PAD * 2,
  height: NODE_SIZE + GROUP_PAD * 2,
}

const LLM_GROUP = {
  x: LLM_PROVIDERS[0].x - LLM_WIDTH / 2 - GROUP_PAD,
  y: ROW2_Y - LLM_HEIGHT / 2 - GROUP_PAD,
  width: LLM_PROVIDERS[2].x - LLM_PROVIDERS[0].x + LLM_WIDTH + GROUP_PAD * 2,
  height: LLM_HEIGHT + GROUP_PAD * 2,
}

const MCP_GROUP = {
  x: MCP_SERVERS[0].x - MCP_SIZE / 2 - GROUP_PAD,
  y: ROW3_Y - MCP_SIZE / 2 - GROUP_PAD,
  width: MCP_SERVERS[5].x - MCP_SERVERS[0].x + MCP_SIZE + GROUP_PAD * 2,
  height: MCP_SIZE + GROUP_PAD * 2,
}

// === HELPER FUNCTIONS ===

function normalizeStep(step: string): string {
  const lower = step.toLowerCase()
  if (lower === 'completed') return 'output'
  return lower
}

function getNodeStatus(
  stepId: string,
  currentStep: string,
  completedSteps: string[],
  cacheHit?: boolean
): NodeStatus {
  const normalizedCurrent = normalizeStep(currentStep)
  const normalizedCompleted = completedSteps.map(normalizeStep)

  // On cache hit, intermediate steps stay idle (not completed)
  if (cacheHit && ['researcher', 'analyzer', 'critic', 'editor', 'a2a'].includes(stepId)) {
    return 'idle'
  }

  if (normalizedCompleted.includes(stepId)) return 'completed'
  if (normalizedCurrent === stepId) return 'executing'
  return 'idle'
}

// === SVG SUB-COMPONENTS ===

function ArrowMarkers() {
  return (
    <defs>
      {['idle', 'executing', 'completed', 'failed'].map((status) => (
        <React.Fragment key={status}>
          {/* Forward arrow (end) */}
          <marker
            id={`arrow-${status}`}
            markerWidth="5"
            markerHeight="5"
            refX="4"
            refY="2.5"
            orient="auto"
            markerUnits="userSpaceOnUse"
          >
            <path d="M0,0 L0,5 L5,2.5 z" fill={`var(--pf-connector-${status})`} />
          </marker>
          {/* Reverse arrow (start) for bidirectional */}
          <marker
            id={`arrow-start-${status}`}
            markerWidth="5"
            markerHeight="5"
            refX="1"
            refY="2.5"
            orient="auto"
            markerUnits="userSpaceOnUse"
          >
            <path d="M5,0 L5,5 L0,2.5 z" fill={`var(--pf-connector-${status})`} />
          </marker>
        </React.Fragment>
      ))}
    </defs>
  )
}

function SVGNode({
  x,
  y,
  icon: Icon,
  label,
  label2,
  status,
  isDiamond = false,
  cacheState,
  isAgent = false,
  hasBorder = true,
  labelPosition = 'below',
  flipIcon = false,
}: {
  x: number
  y: number
  icon: React.ElementType
  label: string
  label2?: string
  status: NodeStatus
  isDiamond?: boolean
  cacheState?: CacheState
  isAgent?: boolean
  hasBorder?: boolean
  labelPosition?: 'above' | 'below'
  flipIcon?: boolean
}) {
  const isExecuting = status === 'executing' || cacheState === 'checking'
  const opacity = status === 'idle' && !cacheState ? 0.7 : status === 'skipped' ? 0.7 : 1
  const strokeWidth = hasBorder ? 1 : 0

  // Label positioning
  const labelY = labelPosition === 'above'
    ? y - NODE_SIZE / 2 - (label2 ? 16 : 8)
    : y + NODE_SIZE / 2 + 10

  return (
    <g opacity={opacity} className="transition-opacity duration-300">
      <rect
        x={x - NODE_SIZE / 2}
        y={y - NODE_SIZE / 2}
        width={NODE_SIZE}
        height={NODE_SIZE}
        rx={isDiamond ? 4 : 8}
        strokeWidth={strokeWidth}
        className={cn(
          "pf-node",
          cacheState ? `pf-cache-${cacheState}` : `pf-node-${status}`,
          isAgent && "pf-agent",
          !hasBorder && "pf-no-border",
          isExecuting && "pf-pulse"
        )}
        transform={isDiamond ? `rotate(45 ${x} ${y})` : undefined}
      />
      <foreignObject
        x={x - ICON_SIZE / 2}
        y={y - ICON_SIZE / 2}
        width={ICON_SIZE}
        height={ICON_SIZE}
      >
        <div className="flex items-center justify-center w-full h-full">
          {isExecuting ? (
            <Loader2 className="w-5 h-5 pf-icon animate-spin" />
          ) : (
            <Icon className="w-5 h-5 pf-icon" style={flipIcon ? { transform: 'scaleX(-1)' } : undefined} />
          )}
        </div>
      </foreignObject>
      <text
        x={x}
        y={labelY}
        textAnchor="middle"
        className={cn(
          "font-medium",
          isAgent ? "text-[9px] pf-text-agent" : "text-[8px] pf-text-label"
        )}
      >
        {label}
        {label2 && (
          <tspan x={x} dy="10">{label2}</tspan>
        )}
      </text>
    </g>
  )
}

// === MAIN COMPONENT ===

export function ProcessFlow({
  currentStep,
  completedSteps,
  mcpStatus,
  llmStatus,
  llmProvider = 'groq',
  cacheHit = false,
  stockSelected = false,
  isSearching = false,
  revisionCount = 0,
  isAborted = false,
}: ProcessFlowProps) {

  // Logic derivations - when aborted, stop all executing states
  const inputStatus = stockSelected ? 'completed' : getNodeStatus('input', currentStep, completedSteps, cacheHit)
  const exchangeStatus = stockSelected ? 'completed' : isSearching ? 'executing' : 'idle'

  // When aborted, freeze agent nodes at their last completed state (no executing)
  const analyzerStatus = isAborted
    ? (completedSteps.includes('analyzer') ? 'completed' : 'idle')
    : getNodeStatus('analyzer', currentStep, completedSteps, cacheHit)
  const criticStatus = isAborted
    ? (completedSteps.includes('critic') ? 'completed' : 'idle')
    : getNodeStatus('critic', currentStep, completedSteps, cacheHit)
  const editorStatus = isAborted
    ? (completedSteps.includes('editor') ? 'completed' : 'idle')
    : getNodeStatus('editor', currentStep, completedSteps, cacheHit)
  const outputStatus = isAborted
    ? (completedSteps.includes('output') ? 'completed' : 'idle')
    : getNodeStatus('output', currentStep, completedSteps, cacheHit)
  const researcherStatus = isAborted
    ? (completedSteps.includes('researcher') ? 'completed' : 'idle')
    : getNodeStatus('researcher', currentStep, completedSteps, cacheHit)
  const a2aStatus = isAborted
    ? (completedSteps.includes('researcher') ? 'completed' : 'idle')
    : (researcherStatus === 'executing' ? 'executing' : researcherStatus === 'completed' ? 'completed' : 'idle')

  const cacheState: CacheState = useMemo(() => {
    if (currentStep === 'cache') return 'checking'
    if (completedSteps.includes('cache')) return cacheHit ? 'hit' : 'miss'
    return 'idle'
  }, [currentStep, completedSteps, cacheHit])

  // Completion halo: workflow completed successfully
  // Editor is optional (only runs if score < 7), so we check for essential steps + output
  const allDone = useMemo(() => {
    const normalizedCompleted = completedSteps.map(normalizeStep)
    const essentialSteps = ['input', 'cache', 'researcher', 'analyzer', 'critic', 'output']
    return essentialSteps.every(s => normalizedCompleted.includes(s))
  }, [completedSteps])

  const conn = (from: NodeStatus | CacheState, to: NodeStatus): NodeStatus => {
    if (from === 'completed' || from === 'miss' || from === 'hit') {
        return to === 'idle' ? 'idle' : to === 'executing' ? 'executing' : 'completed'
    }
    return 'idle'
  }

  // Positioning helpers
  const nodeRight = (n: { x: number }) => n.x + NODE_SIZE / 2 + CONNECTOR_PAD
  const nodeLeft = (n: { x: number }) => n.x - NODE_SIZE / 2 - CONNECTOR_PAD
  const nodeBottom = (n: { y: number }) => n.y + NODE_SIZE / 2 + CONNECTOR_PAD
  const nodeTop = (n: { y: number }) => n.y - NODE_SIZE / 2 - CONNECTOR_PAD
  // Diamond corners (rotated 45°, half-diagonal = NODE_SIZE * sqrt(2) / 2)
  const diamondLeft = (n: { x: number }) => n.x - NODE_SIZE * Math.sqrt(2) / 2 - CONNECTOR_PAD
  const diamondRight = (n: { x: number }) => n.x + NODE_SIZE * Math.sqrt(2) / 2 + CONNECTOR_PAD

  return (
    <div className="h-[260px]">
      <div className="h-full">
        <svg viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} preserveAspectRatio="xMinYMin meet" className="h-full w-auto">
          <ArrowMarkers />

          {/* Group Backgrounds */}
          <rect {...AGENTS_GROUP} rx={8} fill="none" stroke="var(--pf-group-stroke)" strokeWidth={1} strokeDasharray="4 3" opacity={0.35} />
          <rect {...LLM_GROUP} rx={8} fill="none" stroke="var(--pf-group-stroke)" strokeWidth={1} strokeDasharray="4 3" opacity={0.35} />
          <rect {...MCP_GROUP} rx={8} fill="none" stroke="var(--pf-group-stroke)" strokeWidth={1} strokeDasharray="4 3" opacity={0.35} />

          {/* Completion Halo - around OUTPUT node when workflow completes successfully */}
          {allDone && !isAborted && (
            <circle
              cx={NODES.output.x}
              cy={NODES.output.y}
              r={NODE_SIZE / 2 + 8}
              className="pf-success-halo"
            />
          )}

          {/* Row 1 Rightward Connectors */}
          <line x1={nodeRight(NODES.input)} y1={ROW1_Y} x2={diamondLeft(NODES.cache)} y2={ROW1_Y}
                strokeWidth={1.4} markerEnd={`url(#arrow-${conn(inputStatus, cacheState === 'idle' ? 'idle' : 'completed')})`}
                className={cn("pf-connector", `pf-connector-${conn(inputStatus, cacheState === 'idle' ? 'idle' : 'completed')}`)} />
          <line x1={diamondRight(NODES.cache)} y1={ROW1_Y} x2={nodeLeft(NODES.a2a)} y2={ROW1_Y}
                strokeWidth={1.4} markerEnd={`url(#arrow-${cacheState === 'miss' ? conn('miss', a2aStatus) : 'idle'})`}
                className={cn("pf-connector", `pf-connector-${cacheState === 'miss' ? conn('miss', a2aStatus) : 'idle'}`)} />
          <line x1={nodeRight(NODES.a2a)} y1={ROW1_Y} x2={nodeLeft(NODES.analyzer)} y2={ROW1_Y}
                strokeWidth={1.4} markerEnd={`url(#arrow-${conn(a2aStatus, analyzerStatus)})`}
                className={cn("pf-connector", `pf-connector-${conn(a2aStatus, analyzerStatus)}`)} />
          <line x1={nodeRight(NODES.analyzer)} y1={ROW1_Y} x2={nodeLeft(NODES.critic)} y2={ROW1_Y}
                strokeWidth={1.4} markerEnd={`url(#arrow-${conn(analyzerStatus, criticStatus)})`}
                className={cn("pf-connector", `pf-connector-${conn(analyzerStatus, criticStatus)}`)} />
          {/* Critic → Editor connector - only lights up when editor actually runs */}
          <line x1={nodeRight(NODES.critic)} y1={ROW1_Y} x2={nodeLeft(NODES.editor)} y2={ROW1_Y}
                strokeWidth={1.4} markerEnd={`url(#arrow-${editorStatus === 'executing' || editorStatus === 'completed' ? conn(criticStatus, editorStatus) : 'idle'})`}
                className={cn("pf-connector", `pf-connector-${editorStatus === 'executing' || editorStatus === 'completed' ? conn(criticStatus, editorStatus) : 'idle'}`)} />
          {/* Editor → Critic loop (curved path below) - shows when revision loop is active */}
          <path
            d={`M ${NODES.editor.x} ${nodeBottom(NODES.editor)}
                Q ${NODES.editor.x} ${ROW1_Y + 38} ${(NODES.critic.x + NODES.editor.x) / 2} ${ROW1_Y + 38}
                Q ${NODES.critic.x} ${ROW1_Y + 38} ${NODES.critic.x} ${nodeBottom(NODES.critic)}`}
            fill="none"
            strokeWidth={1.4}
            markerEnd={`url(#arrow-${revisionCount > 0 && (editorStatus === 'completed' || criticStatus === 'executing') ? 'completed' : 'idle'})`}
            className={cn("pf-connector", `pf-connector-${revisionCount > 0 && (editorStatus === 'completed' || criticStatus === 'executing') ? 'completed' : 'idle'}`)}
          />
          {/* Editor → Output connector - only lights up when editor ran */}
          <line x1={nodeRight(NODES.editor)} y1={ROW1_Y} x2={nodeLeft(NODES.output)} y2={ROW1_Y}
                strokeWidth={1.4} markerEnd={`url(#arrow-${editorStatus === 'completed' ? conn(editorStatus, outputStatus) : 'idle'})`}
                className={cn("pf-connector", `pf-connector-${editorStatus === 'completed' ? conn(editorStatus, outputStatus) : 'idle'}`)} />
          {/* Critic → Output direct path (curved above) - shows when editor is skipped */}
          <path
            d={`M ${nodeRight(NODES.critic)} ${ROW1_Y - 8}
                Q ${(NODES.critic.x + NODES.output.x) / 2} ${ROW1_Y - 28} ${nodeLeft(NODES.output)} ${ROW1_Y - 8}`}
            fill="none"
            strokeWidth={1.4}
            markerEnd={`url(#arrow-${editorStatus === 'idle' && criticStatus === 'completed' ? conn(criticStatus, outputStatus) : 'idle'})`}
            className={cn("pf-connector", `pf-connector-${editorStatus === 'idle' && criticStatus === 'completed' ? conn(criticStatus, outputStatus) : 'idle'}`)}
          />

          {/* Researcher ↔ MCP block connector (bidirectional) */}
          <line x1={nodeRight(NODES.researcher)} y1={ROW3_Y} x2={MCP_GROUP.x - 2} y2={ROW3_Y}
                strokeWidth={1.4}
                markerStart={`url(#arrow-start-${researcherStatus === 'executing' || researcherStatus === 'completed' ? 'completed' : 'idle'})`}
                markerEnd={`url(#arrow-${researcherStatus === 'executing' || researcherStatus === 'completed' ? 'completed' : 'idle'})`}
                className={cn("pf-connector", `pf-connector-${researcherStatus === 'executing' || researcherStatus === 'completed' ? 'completed' : 'idle'}`)} />

          {/* Bidirectional Vertical Connectors */}
          {/* User Input ↔ Exchange */}
          <line x1={NODES.input.x} y1={nodeBottom(NODES.input)} x2={NODES.exchange.x} y2={nodeTop(NODES.exchange)}
                strokeWidth={1.4}
                markerStart={`url(#arrow-start-${conn(exchangeStatus, inputStatus)})`}
                markerEnd={`url(#arrow-${conn(inputStatus, exchangeStatus)})`}
                className={cn("pf-connector", `pf-connector-${inputStatus === 'completed' || exchangeStatus === 'completed' ? 'completed' : 'idle'}`)} />

          {/* A2A ↔ Researcher */}
          <line x1={NODES.a2a.x} y1={nodeBottom(NODES.a2a)} x2={NODES.researcher.x} y2={nodeTop(NODES.researcher)}
                strokeWidth={1.4}
                markerStart={`url(#arrow-start-${conn(researcherStatus, a2aStatus)})`}
                markerEnd={`url(#arrow-${conn(a2aStatus, researcherStatus)})`}
                className={cn("pf-connector", `pf-connector-${a2aStatus === 'completed' || researcherStatus === 'completed' ? 'completed' : a2aStatus === 'executing' || researcherStatus === 'executing' ? 'executing' : 'idle'}`)} />

          {/* Agent Group ↔ LLM Group (Orchestration connector) */}
          <line x1={AGENTS_CENTER_X} y1={AGENTS_GROUP.y + AGENTS_GROUP.height + 2} x2={AGENTS_CENTER_X} y2={LLM_GROUP.y - 2}
                markerStart={`url(#arrow-start-${analyzerStatus === 'executing' || criticStatus === 'executing' || editorStatus === 'executing' ? 'executing' : analyzerStatus === 'completed' ? 'completed' : 'idle'})`}
                markerEnd={`url(#arrow-${analyzerStatus === 'executing' || criticStatus === 'executing' || editorStatus === 'executing' ? 'executing' : analyzerStatus === 'completed' ? 'completed' : 'idle'})`}
                className={cn("pf-connector pf-orchestration", `pf-connector-${analyzerStatus === 'executing' || criticStatus === 'executing' || editorStatus === 'executing' ? 'executing' : analyzerStatus === 'completed' ? 'completed' : 'idle'}`)} />

          {/* Row 1 Nodes - labels above */}
          <SVGNode x={NODES.input.x} y={NODES.input.y} icon={User} label="User Input" status={inputStatus} labelPosition="above" />
          <SVGNode x={NODES.cache.x} y={NODES.cache.y} icon={Database} label="Cache" status={cacheState === 'idle' ? 'idle' : 'completed'} isDiamond cacheState={cacheState} labelPosition="above" />
          <SVGNode x={NODES.a2a.x} y={NODES.a2a.y} icon={Network} label="A2A client" status={a2aStatus} labelPosition="above" />
          <SVGNode x={NODES.analyzer.x} y={NODES.analyzer.y} icon={Brain} label="Analyzer" label2="Agent" status={analyzerStatus} isAgent labelPosition="above" />
          <SVGNode x={NODES.critic.x} y={NODES.critic.y} icon={MessageSquare} label="Critic" label2="Agent" status={criticStatus} isAgent labelPosition="above" />
          <SVGNode x={NODES.editor.x} y={NODES.editor.y} icon={Edit3} label="Editor" label2="Agent" status={editorStatus} isAgent labelPosition="above" />
          <SVGNode x={NODES.output.x} y={NODES.output.y} icon={FileOutput} label="Output" status={outputStatus} labelPosition="above" flipIcon />

          {/* Row 2 & 3 Nodes - labels below */}
          <SVGNode x={NODES.exchange.x} y={NODES.exchange.y} icon={GitBranch} label="Exchange" label2="Database" status={exchangeStatus} />
          <SVGNode x={NODES.researcher.x} y={NODES.researcher.y} icon={Search} label="Researcher" label2="Agent" status={researcherStatus} isAgent />

          {/* LLM Providers - with borders */}
          {LLM_PROVIDERS.map((llm) => {
            // Check actual provider status from backend
            const providerStatus = llmStatus?.[llm.id as keyof LLMStatus];
            const isFailed = providerStatus === 'failed';
            const isProviderCompleted = providerStatus === 'completed';

            // Only show executing if agents are active AND this provider hasn't failed/completed yet
            const agentsActive = analyzerStatus === 'executing' || criticStatus === 'executing' || editorStatus === 'executing';
            const isActive = agentsActive && !isFailed && !isProviderCompleted;

            // Only the actually used provider shows as completed (from backend llmStatus)
            const status = isFailed ? 'failed' : isProviderCompleted ? 'completed' : isActive ? 'executing' : 'idle';
            return (
              <g key={llm.id}>
                <rect
                  x={llm.x - LLM_WIDTH / 2}
                  y={ROW2_Y - LLM_HEIGHT / 2}
                  width={LLM_WIDTH}
                  height={LLM_HEIGHT}
                  rx={4}
                  strokeWidth={1}
                  className={cn("pf-llm", `pf-llm-${status}`, status === 'executing' && "pf-pulse")}
                />
                <text
                  x={llm.x}
                  y={ROW2_Y + 4}
                  textAnchor="middle"
                  className={`text-[9px] font-medium pf-llm-text-${status}`}
                >
                  {llm.name}
                </text>
              </g>
            )
          })}

          {/* MCP Servers */}
          {MCP_SERVERS.map((mcp) => {
            // Check actual MCP status from backend
            const serverStatus = mcpStatus[mcp.id as keyof MCPStatus];
            const isFailed = serverStatus === 'failed';
            const isPartial = serverStatus === 'partial';
            const isServerCompleted = serverStatus === 'completed';

            // Determine visual status: failed/partial take precedence (persist for session)
            const status = isFailed ? 'failed' :
                          isPartial ? 'partial' :
                          isServerCompleted ? 'completed' :
                          researcherStatus === 'executing' ? 'executing' : 'idle';
            const Icon = mcp.icon;
            return (
              <g key={mcp.id} opacity={status === 'failed' || status === 'partial' ? 0.9 : status === 'executing' ? 1 : status === 'completed' ? 0.85 : 0.6}>
                <rect x={mcp.x - MCP_SIZE / 2} y={ROW3_Y - MCP_SIZE / 2} width={MCP_SIZE} height={MCP_SIZE} rx={4}
                      strokeWidth={1}
                      className={cn("pf-node pf-node-mcp",
                        status === 'failed' ? 'pf-node-failed' :
                        status === 'partial' ? 'pf-node-partial' :
                        status === 'executing' ? 'pf-node-executing pf-pulse' :
                        status === 'completed' ? 'pf-node-completed' : 'pf-node-idle')} />
                <foreignObject
                  x={mcp.x - MCP_ICON_SIZE / 2}
                  y={ROW3_Y - MCP_ICON_SIZE / 2}
                  width={MCP_ICON_SIZE}
                  height={MCP_ICON_SIZE}
                >
                  <div className="flex items-center justify-center w-full h-full">
                    <Icon className={cn("w-4 h-4",
                      status === 'failed' ? 'text-red-400' :
                      status === 'partial' ? 'text-amber-400' : 'pf-icon')} />
                  </div>
                </foreignObject>
                <text x={mcp.x} y={MCP_GROUP.y + MCP_GROUP.height + 12} textAnchor="middle"
                      className={cn("text-[8px] font-medium",
                        status === 'failed' ? 'fill-red-400' :
                        status === 'partial' ? 'fill-amber-400' : 'pf-text-label')}>{mcp.label}</text>
              </g>
            )
          })}

          {/* MCP Group Label */}
          <text
            x={MCP_GROUP.x + MCP_GROUP.width / 2}
            y={MCP_GROUP.y - 6}
            textAnchor="middle"
            className="text-[9px] font-medium pf-group-label"
          >
            Custom MCP Servers
          </text>
        </svg>

      </div>
    </div>
  )
}

export default ProcessFlow
