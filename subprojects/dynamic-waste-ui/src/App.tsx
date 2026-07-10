// 本文件实现建筑废弃物多智能体分拣系统的单屏监控与人工控制界面。
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  Bot,
  Boxes,
  Check,
  CircleHelp,
  Cpu,
  Database,
  Eye,
  GitBranch,
  Layers3,
  Network,
  Play,
  Radar,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  UserCheck,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  agentTrace,
  agentTraceRuns,
  graphEdges as fallbackGraphEdges,
  graphNodes as fallbackGraphNodes,
  instances as fallbackInstances,
  runStatus,
  type AgentTraceNode,
  type AgentTraceRun,
  type GraphNode,
} from "./data/mockDashboard";
import {
  buildRos2CommandPreview,
  canSendToRos2,
  deriveReviewQueue,
  getConnectedGraphNodeIds,
  resolveInstanceIdFromGraphNode,
  type DashboardView,
  type ReviewQueueItem,
  type WasteInstance,
} from "./lib/dashboard";
import { adaptKnowledgeGraphSnapshot, type AdaptedKgDashboardData, type KgSnapshot } from "./lib/kgAdapter";

const navItems: Array<{ id: DashboardView; label: string; icon: LucideIcon }> = [
  { id: "overview", label: "系统总览", icon: Activity },
  { id: "trace", label: "智能体追踪", icon: GitBranch },
  { id: "sim", label: "仿真界面", icon: Bot },
  { id: "kg", label: "知识图谱", icon: Network },
  { id: "review", label: "人工复核", icon: UserCheck },
  { id: "ros2", label: "ROS2 桥接", icon: Send },
];

export default function App() {
  const requestedView = new URLSearchParams(window.location.search).get("view") as DashboardView | null;
  const [activeView, setActiveView] = useState<DashboardView>(navItems.some((item) => item.id === requestedView) ? requestedView! : "overview");
  const [selectedAgentId, setSelectedAgentId] = useState("supervisor");
  const [selectedRunId, setSelectedRunId] = useState("risk_gate");
  const [selectedInstanceId, setSelectedInstanceId] = useState("glass_02");
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState("glass_02");
  const [reviewAction, setReviewAction] = useState("等待人工确认");
  const [kgData, setKgData] = useState<AdaptedKgDashboardData | null>(null);
  const [kgLoadStatus, setKgLoadStatus] = useState<"loading" | "loaded" | "fallback">("loading");

  useEffect(() => {
    let active = true;
    fetch("/data/kg-snapshot.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`KG snapshot HTTP ${response.status}`);
        return response.json() as Promise<KgSnapshot>;
      })
      .then((snapshot) => {
        if (!active) return;
        const adapted = adaptKnowledgeGraphSnapshot(snapshot);
        setKgData(adapted);
        setKgLoadStatus("loaded");
      })
      .catch(() => {
        if (active) setKgLoadStatus("fallback");
      });
    return () => {
      active = false;
    };
  }, []);

  const instances = kgData?.instances ?? fallbackInstances;
  const graphNodes = kgData?.graphNodes ?? fallbackGraphNodes;
  const graphEdges = kgData?.graphEdges ?? fallbackGraphEdges;
  const reviewQueue = useMemo(() => deriveReviewQueue(instances), [instances]);
  const selectedAgent = agentTrace.find((node) => node.id === selectedAgentId) ?? agentTrace[0];
  const selectedRun = agentTraceRuns.find((run) => run.id === selectedRunId) ?? agentTraceRuns[0];
  const selectedInstance = instances.find((item) => item.instance_id === selectedInstanceId) ?? instances[0];
  const selectedGraphNode = graphNodes.find((node) => node.id === selectedGraphNodeId) ?? graphNodes[0];
  const connectedGraphNodeIds = useMemo(
    () => getConnectedGraphNodeIds(graphEdges, selectedGraphNode.id),
    [graphEdges, selectedGraphNode.id],
  );
  const ros2Preview = buildRos2CommandPreview(selectedInstance);

  function selectInstance(instanceId: string) {
    setSelectedInstanceId(instanceId);
    if (graphNodes.some((node) => node.id === instanceId)) setSelectedGraphNodeId(instanceId);
    setReviewAction("等待人工确认");
  }

  function selectGraphNode(node: GraphNode) {
    setSelectedGraphNodeId(node.id);
    const instanceId = resolveInstanceIdFromGraphNode(node.id, instances);
    if (instanceId) selectInstance(instanceId);
  }

  const commonProps = {
    instances,
    graphNodes,
    graphEdges,
    reviewQueue,
    selectedInstance,
    selectedGraphNode,
    connectedGraphNodeIds,
    ros2Preview,
    selectInstance,
    selectGraphNode,
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand-block">
          <span className="brand-mark"><Boxes size={20} /></span>
          <div><strong>WasteOps</strong><small>robot sorting</small></div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={activeView === item.id ? "nav-item active" : "nav-item"}
              title={item.label}
              onClick={() => setActiveView(item.id)}
              type="button"
            >
              <item.icon size={17} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={kgLoadStatus === "loaded" ? "live-dot online" : "live-dot"} />
          <span>{kgLoadStatus === "loaded" ? "KG 快照已接入" : kgLoadStatus === "loading" ? "正在读取 KG" : "KG 演示数据"}</span>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">DYNAMIC WASTE CONTROL</p>
            <h1>建筑废弃物分拣控制台</h1>
          </div>
          <div className="status-strip" aria-label="系统状态">
            <StatusPill icon={Radar} label={runStatus.task} tone="teal" />
            <StatusPill icon={Eye} label={runStatus.camera} tone="green" />
            <StatusPill icon={Send} label={`ROS2 ${runStatus.ros2}`} tone="slate" />
            <StatusPill icon={Cpu} label={`GPU ${runStatus.gpu}`} tone="slate" />
          </div>
        </header>

        <div className={`content-stage view-${activeView}`}>
          {activeView === "overview" && (
            <OverviewWorkspace
              {...commonProps}
              selectedAgent={selectedAgent}
              onSelectAgent={setSelectedAgentId}
              kgLoadStatus={kgLoadStatus}
              onOpenView={setActiveView}
            />
          )}
          {activeView === "trace" && <TraceWorkspace selectedRun={selectedRun} onSelectRun={setSelectedRunId} onSelectInstance={selectInstance} />}
          {activeView === "sim" && <SimulationWorkspace instances={instances} selectedInstance={selectedInstance} onSelectInstance={selectInstance} />}
          {activeView === "kg" && (
            <KnowledgeWorkspace
              {...commonProps}
              kgLoadStatus={kgLoadStatus}
            />
          )}
          {activeView === "review" && (
            <ReviewWorkspace
              reviewQueue={reviewQueue}
              selectedInstance={selectedInstance}
              ros2Preview={ros2Preview}
              reviewAction={reviewAction}
              onSelectInstance={selectInstance}
              onReviewAction={setReviewAction}
            />
          )}
          {activeView === "ros2" && <Ros2Workspace instance={selectedInstance} preview={ros2Preview} onSelectInstance={selectInstance} instances={instances} />}
        </div>
      </main>
    </div>
  );
}

interface WorkspaceDataProps {
  instances: WasteInstance[];
  graphNodes: GraphNode[];
  graphEdges: Array<{ from: string; to: string }>;
  reviewQueue: ReviewQueueItem[];
  selectedInstance: WasteInstance;
  selectedGraphNode: GraphNode;
  connectedGraphNodeIds: Set<string>;
  ros2Preview: ReturnType<typeof buildRos2CommandPreview>;
  selectInstance: (id: string) => void;
  selectGraphNode: (node: GraphNode) => void;
}

function OverviewWorkspace({
  instances,
  reviewQueue,
  selectedInstance,
  selectedAgent,
  onSelectAgent,
  selectInstance,
  kgLoadStatus,
  onOpenView,
}: WorkspaceDataProps & {
  selectedAgent: AgentTraceNode;
  onSelectAgent: (id: string) => void;
  kgLoadStatus: "loading" | "loaded" | "fallback";
  onOpenView: (view: DashboardView) => void;
}) {
  return (
    <div className="overview-layout">
      <Panel className="architecture-panel" icon={GitBranch} title="多智能体任务流" meta="4 个智能体 · KG 是共享状态底座">
        <AgentArchitecture selectedAgent={selectedAgent} onSelectAgent={onSelectAgent} />
      </Panel>
      <div className="overview-lower">
        <Panel className="overview-sim" icon={Bot} title="仿真 / 相机视图" meta="仿真接口待接入">
          <SimulationViewport instances={instances} selectedInstanceId={selectedInstance.instance_id} onSelectInstance={selectInstance} />
        </Panel>
        <div className="overview-side">
            <Panel className="compact-state-panel" icon={Database} title="知识图谱状态" meta={kgLoadStatus === "loaded" ? "JSON snapshot" : kgLoadStatus === "loading" ? "loading" : "fallback"} actionLabel="查看图谱" onAction={() => onOpenView("kg")}>
            <InstanceStateCard instance={selectedInstance} />
          </Panel>
          <Panel className="compact-review-panel" icon={UserCheck} title="人工复核" meta={`${reviewQueue.length} 个待处理`} actionLabel="进入复核" onAction={() => onOpenView("review")}>
            <CompactReviewList queue={reviewQueue} selectedId={selectedInstance.instance_id} onSelect={selectInstance} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

function AgentArchitecture({ selectedAgent, onSelectAgent }: { selectedAgent: AgentTraceNode; onSelectAgent: (id: string) => void }) {
  const byId = (id: string) => agentTrace.find((agent) => agent.id === id)!;
  return (
    <div className="architecture-map">
      <button className={`supervisor-card agent-card ${selectedAgent.id === "supervisor" ? "selected" : ""}`} onClick={() => onSelectAgent("supervisor")} type="button">
        <Bot size={17} /><span><strong>Supervisor Agent</strong><small>目标分解 · 流程调度 · 重规划触发</small></span><Badge tone="green">运行中</Badge>
      </button>
      <div className="dispatch-label">调度与状态回收</div>
      <div className="primary-flow">
        <FlowAgent agent={byId("perception")} selected={selectedAgent.id === "perception"} onSelect={onSelectAgent} index="01" />
        <FlowArrow label="观测事件" />
        <button className="flow-card kg-component" onClick={() => onSelectAgent("kg_state")} type="button">
          <Database size={17} /><span><strong>知识图谱状态</strong><small>长期知识 · 场景记忆 · 事件日志</small></span><em>规划评分不写入 KG</em>
        </button>
        <FlowArrow label="graph_state" />
        <FlowAgent agent={byId("action_planner")} selected={selectedAgent.id === "action_planner"} onSelect={onSelectAgent} index="03" />
        <FlowArrow label="结构化计划" />
        <div className="execution-branch">
          <span className="human-gate-label"><UserCheck size={13} /> 人工门控</span>
          <FlowAgent agent={byId("execution")} selected={selectedAgent.id === "execution"} onSelect={onSelectAgent} index="04" />
          <span className="ros2-label"><Send size={12} /> ROS2 Bridge</span>
        </div>
      </div>
      <div className="feedback-line"><RotateCcw size={13} /> 执行结果与人工确认写入 EventLog，Supervisor 根据新状态继续或重规划</div>
      <div className="agent-boundary"><strong>{selectedAgent.title}</strong><span>{selectedAgent.decision}</span></div>
    </div>
  );
}

function FlowAgent({ agent, selected, onSelect, index }: { agent: AgentTraceNode; selected: boolean; onSelect: (id: string) => void; index: string }) {
  return (
    <button className={`flow-card agent-card ${selected ? "selected" : ""}`} onClick={() => onSelect(agent.id)} type="button">
      <span className="agent-index">{index}</span><Bot size={17} /><span><strong>{agent.title}</strong><small>{agent.subtitle}</small></span>
    </button>
  );
}

function FlowArrow({ label }: { label: string }) {
  return <span className="flow-arrow"><small>{label}</small><ArrowRight size={18} /></span>;
}

function TraceWorkspace({ selectedRun, onSelectRun, onSelectInstance }: { selectedRun: AgentTraceRun; onSelectRun: (id: string) => void; onSelectInstance: (id: string) => void }) {
  const visibleRuns = agentTraceRuns.filter((run) => run.parentId !== null);
  return (
    <Panel className="full-panel trace-workspace" icon={GitBranch} title="LangGraph 智能体追踪" meta="智能体为蓝色，系统组件与门控为灰色">
      <div className="trace-agent-strip">
        {agentTraceRuns.filter((run) => run.runType === "agent" && !run.retryOf).map((run) => (
          <button key={run.id} className={selectedRun.id === run.id ? "active" : ""} onClick={() => onSelectRun(run.id)} type="button"><Bot size={15} /><span>{run.title}</span><small>{run.durationMs} ms</small></button>
        ))}
      </div>
      <div className="trace-body">
        <div className="trace-list" aria-label="运行节点列表">
          {visibleRuns.map((run) => (
            <button key={run.id} className={`trace-row ${run.runType} ${run.status} ${selectedRun.id === run.id ? "selected" : ""}`} onClick={() => onSelectRun(run.id)} type="button">
              <span className="trace-status" /><span className="trace-title"><strong>{run.title}</strong><small>{run.runType} · {run.phase}</small></span><span>{run.durationMs} ms</span>
            </button>
          ))}
        </div>
        <div className="trace-detail">
          <div className="detail-heading"><div><span className={`run-type ${selectedRun.runType}`}>{selectedRun.runType}</span><h3>{selectedRun.title}</h3></div><Badge tone={selectedRun.status === "blocked" ? "red" : selectedRun.status === "success" ? "green" : "amber"}>{selectedRun.status}</Badge></div>
          <KeyValue label="输入" value={selectedRun.input} />
          <KeyValue label="输出" value={selectedRun.output} />
          <div className="detail-meta"><span>阶段：{selectedRun.phase}</span><span>耗时：{selectedRun.durationMs} ms</span>{selectedRun.retryOf && <span>重试自：{selectedRun.retryOf}</span>}</div>
          <div className="linked-row">{selectedRun.linkedInstanceIds.map((id) => <button key={id} onClick={() => onSelectInstance(id)} type="button">{id}</button>)}</div>
          <div className="feedback-explain"><RotateCcw size={15} /><span>失败或人工复核结果会先更新 KG 事件层，再触发 Supervisor 和 Action Planning Agent 重规划。</span></div>
        </div>
      </div>
    </Panel>
  );
}

function SimulationWorkspace({ instances, selectedInstance, onSelectInstance }: { instances: WasteInstance[]; selectedInstance: WasteInstance; onSelectInstance: (id: string) => void }) {
  return (
    <div className="focus-two-column">
      <Panel className="full-panel" icon={Bot} title="仿真 / 数字孪生" meta="后续接入 Gazebo 或 Isaac Sim">
        <SimulationViewport instances={instances} selectedInstanceId={selectedInstance.instance_id} onSelectInstance={onSelectInstance} />
      </Panel>
      <Panel className="full-panel object-list-panel" icon={Eye} title="场景实例" meta={`${instances.length} detected`}>
        {instances.map((instance) => <InstanceButton key={instance.instance_id} instance={instance} selected={instance.instance_id === selectedInstance.instance_id} onSelect={onSelectInstance} />)}
        <InstanceStateCard instance={selectedInstance} />
      </Panel>
    </div>
  );
}

function KnowledgeWorkspace({ instances, graphNodes, graphEdges, selectedInstance, selectedGraphNode, connectedGraphNodeIds, selectGraphNode, kgLoadStatus }: WorkspaceDataProps & { kgLoadStatus: "loading" | "loaded" | "fallback" }) {
  return (
    <div className="kg-workspace">
      <Panel className="full-panel kg-main-panel" icon={Network} title="知识图谱局部状态" meta={kgLoadStatus === "loaded" ? "已接入项目 KG 快照" : "演示数据"}>
        <KgLayerSummary instances={instances} nodes={graphNodes} />
        <KnowledgeGraphView nodes={graphNodes} edges={graphEdges} selectedNodeId={selectedGraphNode.id} connectedNodeIds={connectedGraphNodeIds} onSelectNode={selectGraphNode} />
      </Panel>
      <Panel className="full-panel kg-inspector-panel" icon={Layers3} title="实例状态谓词" meta={selectedInstance.instance_id}>
        <InstanceStateCard instance={selectedInstance} expanded />
        <div className="kg-boundary-note"><ShieldAlert size={15} /><span>KG 保存事实、状态、约束和类别属性；动作顺序、重试策略仍由规划智能体生成。</span></div>
        <GraphNodeInspector node={selectedGraphNode} />
      </Panel>
    </div>
  );
}

function ReviewWorkspace({ reviewQueue, selectedInstance, ros2Preview, reviewAction, onSelectInstance, onReviewAction }: { reviewQueue: ReviewQueueItem[]; selectedInstance: WasteInstance; ros2Preview: ReturnType<typeof buildRos2CommandPreview>; reviewAction: string; onSelectInstance: (id: string) => void; onReviewAction: (action: string) => void }) {
  const selectedReview = reviewQueue.find((item) => item.instance_id === selectedInstance.instance_id);
  return (
    <Panel className="full-panel review-workspace" icon={UserCheck} title="人工复核工作台" meta={`${reviewQueue.length} 个对象等待确认`}>
      <div className="review-layout">
        <div className="review-queue">{reviewQueue.map((item) => <InstanceButton key={item.instance_id} instance={item} selected={item.instance_id === selectedInstance.instance_id} onSelect={onSelectInstance} />)}</div>
        <div className="review-object"><div className={`object-preview ${selectedInstance.candidate_class}`}><span>{selectedInstance.candidate_class}</span></div><InstanceStateCard instance={selectedInstance} /></div>
        <div className="review-controls">
          <h3>复核原因</h3><div className="reason-row">{(selectedReview?.review_reasons ?? ["not_in_review_queue"]).map((reason) => <Badge key={reason} tone={reason.includes("conflict") ? "red" : "amber"}>{reason}</Badge>)}</div>
          <GateChecklist preview={ros2Preview} />
          <div className="action-row">
            <button className="command approve" onClick={() => onReviewAction("已确认：等待写入 HumanReviewEvent")} type="button"><Check size={15} />确认</button>
            <button className="command unknown" onClick={() => onReviewAction("设置 recognition_status=unknown")} type="button"><CircleHelp size={15} />标记未知</button>
            <button className="command reject" onClick={() => onReviewAction("已拒绝：等待写入 rejected 状态")} type="button"><X size={15} />拒绝</button>
          </div>
          <div className="review-action-status"><RefreshCw size={14} /><span>{reviewAction}</span></div>
        </div>
      </div>
    </Panel>
  );
}

function Ros2Workspace({ instance, preview, instances, onSelectInstance }: { instance: WasteInstance; preview: ReturnType<typeof buildRos2CommandPreview>; instances: WasteInstance[]; onSelectInstance: (id: string) => void }) {
  return (
    <div className="focus-two-column ros2-workspace">
      <Panel className="full-panel object-list-panel" icon={Database} title="执行候选" meta="结构化请求">
        {instances.map((item) => <InstanceButton key={item.instance_id} instance={item} selected={item.instance_id === instance.instance_id} onSelect={onSelectInstance} />)}
      </Panel>
      <Panel className="full-panel" icon={Send} title="ROS2 Bridge 预览" meta={preview.status}>
        <div className="ros2-preview"><GateChecklist preview={preview} /><pre>{JSON.stringify(preview, null, 2)}</pre><button className="command ros2" disabled={!canSendToRos2(instance)} type="button"><Send size={15} />发送结构化命令</button><p>当前仅为接口预览，尚未验证真实机械臂闭环。</p></div>
      </Panel>
    </div>
  );
}

function Panel({ icon: Icon, title, meta, className = "", actionLabel, onAction, children }: { icon: LucideIcon; title: string; meta: string; className?: string; actionLabel?: string; onAction?: () => void; children: ReactNode }) {
  return <section className={`panel ${className}`}><div className="panel-header"><div className="panel-title"><Icon size={17} /><h2>{title}</h2></div><div className="panel-meta"><span>{meta}</span>{actionLabel && <button onClick={onAction} type="button">{actionLabel}<ArrowRight size={13} /></button>}</div></div>{children}</section>;
}

function StatusPill({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone: string }) {
  return <span className={`status-pill ${tone}`}><Icon size={13} />{label}</span>;
}

function InstanceButton({ instance, selected, onSelect }: { instance: WasteInstance; selected: boolean; onSelect: (id: string) => void }) {
  return <button className={`instance-button ${selected ? "selected" : ""}`} onClick={() => onSelect(instance.instance_id)} type="button"><span className={`instance-dot ${instance.recognition_status}`} /><span><strong>{instance.instance_id}</strong><small>{instance.candidate_class} · {instance.recognition_status}</small></span><Badge tone={canSendToRos2(instance) ? "green" : "amber"}>{canSendToRos2(instance) ? "可执行" : "受控"}</Badge></button>;
}

function InstanceStateCard({ instance, expanded = false }: { instance: WasteInstance; expanded?: boolean }) {
  const rows = [
    ["candidate_class (关系)", instance.candidate_class], ["recognition_status", instance.recognition_status], ["current_handling_policy", instance.current_handling_policy],
    ["task_status", instance.task_status], ["depth_valid_ratio", instance.depth_valid_ratio.toFixed(2)], ["occlusion_state", instance.occlusion_state],
  ];
  if (expanded) rows.push(["vlm_consistency", instance.vlm_consistency], ["attempt_count", String(instance.attempt_count)], ["can_enter_ros2", String(canSendToRos2(instance))]);
  return <div className="instance-state"><div className="state-heading"><div><strong>{instance.instance_id}</strong><small>当前实例状态</small></div><Badge tone={canSendToRos2(instance) ? "green" : "amber"}>{canSendToRos2(instance) ? "READY" : "GATED"}</Badge></div><dl>{rows.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></div>;
}

function CompactReviewList({ queue, selectedId, onSelect }: { queue: ReviewQueueItem[]; selectedId: string; onSelect: (id: string) => void }) {
  return <div className="compact-review-list">{queue.slice(0, 3).map((item) => <button key={item.instance_id} className={selectedId === item.instance_id ? "selected" : ""} onClick={() => onSelect(item.instance_id)} type="button"><AlertIcon status={item.vlm_consistency} /><span><strong>{item.instance_id}</strong><small>{item.review_reasons.slice(0, 2).join(" · ")}</small></span><ArrowRight size={14} /></button>)}</div>;
}

function AlertIcon({ status }: { status: string }) { return status === "conflict" ? <ShieldAlert size={16} /> : <CircleHelp size={16} />; }

function KgLayerSummary({ instances, nodes }: { instances: WasteInstance[]; nodes: GraphNode[] }) {
  const categories = nodes.filter((node) => node.kind === "category").length;
  return <div className="kg-layer-summary"><div><span>长期知识</span><strong>{categories} 类</strong><small>类别先验与处理权限</small></div><ArrowRight size={15} /><div><span>短期记忆</span><strong>{instances.length} 实例</strong><small>Scene、实例与 unknown</small></div><ArrowRight size={15} /><div><span>事件日志</span><strong>Append-only</strong><small>7 类固定事件节点</small></div></div>;
}

function KnowledgeGraphView({ nodes, edges, selectedNodeId, connectedNodeIds, onSelectNode }: { nodes: GraphNode[]; edges: Array<{ from: string; to: string }>; selectedNodeId: string; connectedNodeIds: Set<string>; onSelectNode: (node: GraphNode) => void }) {
  const selected = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];
  const neighbours = nodes.filter((node) => node.id !== selected.id && connectedNodeIds.has(node.id)).slice(0, 7);
  const visible = [selected, ...neighbours];
  const positions = new Map<string, { x: number; y: number }>();
  positions.set(selected.id, { x: 320, y: 155 });
  neighbours.forEach((node, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / Math.max(neighbours.length, 1);
    positions.set(node.id, { x: 320 + Math.cos(angle) * 220, y: 155 + Math.sin(angle) * 105 });
  });
  const visibleIds = new Set(visible.map((node) => node.id));
  return <div className="kg-canvas"><svg viewBox="0 0 640 310" role="img" aria-label="选中节点的知识图谱局部关系">
    <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" /></marker></defs>
    {edges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to)).map((edge) => { const from = positions.get(edge.from)!; const to = positions.get(edge.to)!; return <line key={`${edge.from}-${edge.to}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} markerEnd="url(#arrow)" />; })}
    {visible.map((node) => { const point = positions.get(node.id)!; const label = node.label.length > 22 ? `${node.label.slice(0, 20)}…` : node.label; return <g key={node.id} className={`svg-node ${node.kind} ${node.id === selected.id ? "selected" : ""}`} transform={`translate(${point.x},${point.y})`} role="button" tabIndex={0} onClick={() => onSelectNode(node)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelectNode(node); }}><rect x="-68" y="-20" width="136" height="40" rx="6" /><text textAnchor="middle" dominantBaseline="middle">{label}</text></g>; })}
  </svg><span className="kg-canvas-caption">仅展示选中节点的一跳关系，避免完整图谱挤出画布</span></div>;
}

function GraphNodeInspector({ node }: { node: GraphNode }) { return <div className="graph-node-inspector"><div><strong>{node.label}</strong><span>{node.kind}</span></div><p>{node.description}</p></div>; }

function SimulationViewport({ instances, selectedInstanceId, onSelectInstance }: { instances: WasteInstance[]; selectedInstanceId: string; onSelectInstance: (id: string) => void }) {
  return <div className="sim-viewport"><div className="camera-frustum" /><div className="robot-arm"><span className="joint base" /><span className="arm upper" /><span className="joint elbow" /><span className="arm lower" /><span className="gripper" /></div><div className="lab-table">{instances.slice(0, 4).map((instance, index) => <Debris key={instance.instance_id} className={`debris item-${index} ${instance.candidate_class}`} id={instance.instance_id} selected={selectedInstanceId === instance.instance_id} onSelect={onSelectInstance} />)}</div><div className="viewport-hud left"><span>D435i frame</span><strong>camera_color_optical_frame</strong></div><div className="viewport-hud right"><span>Selected</span><strong>{selectedInstanceId}</strong></div><div className="timeline"><button title="回放" type="button"><Play size={14} /></button><div><span /></div><small>00:14 / 01:20</small></div></div>;
}

function Debris({ className, id, selected, onSelect }: { className: string; id: string; selected: boolean; onSelect: (id: string) => void }) { return <button className={`${className} ${selected ? "selected" : ""}`} onClick={() => onSelect(id)} type="button"><span>{id}</span></button>; }

function GateChecklist({ preview }: { preview: ReturnType<typeof buildRos2CommandPreview> }) { return <div className="gate-list">{Object.entries(preview.gate).map(([key, passed]) => <span key={key} className={passed ? "gate-pass" : "gate-block"}>{passed ? <Check size={11} /> : <X size={11} />}{key}</span>)}</div>; }

function KeyValue({ label, value }: { label: string; value: string }) { return <div className="key-value"><span>{label}</span><strong>{value}</strong></div>; }

function Badge({ children, tone }: { children: ReactNode; tone: "amber" | "green" | "red" }) { return <span className={`badge ${tone}`}>{children}</span>; }
