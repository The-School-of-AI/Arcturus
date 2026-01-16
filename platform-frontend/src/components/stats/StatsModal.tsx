import React, { useEffect, useState } from 'react';
import { X, TrendingUp, DollarSign, Zap, Clock, RefreshCw, LayoutDashboard, Users, Lightbulb, CheckCircle, XCircle, AlertTriangle, Activity, Target, Wrench, Globe, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';
import { useTheme } from '@/components/theme';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    LineChart, Line, PieChart, Pie, Cell, AreaChart, Area, Legend
} from 'recharts';

// Extended metrics interface for fleet telemetry
interface FleetMetrics {
    last_updated: string;
    totals: {
        total_runs: number;
        unique_queries: number;
        total_cost: number;
        total_tokens: number;
        avg_cost: number;
        median_cost: number;
        p95_cost: number;
        avg_duration_sec: number;
        p95_duration_sec: number;
        outcomes: {
            success: number;
            partial: number;
            failed: number;
            aborted: number;
            running: number;
        };
        success_rate: number;
    };
    agents: Record<string, {
        calls: number;
        avg_tokens: number;
        avg_cost: number;
        total_cost: number;
        success_rate: number;
        retry_rate: number;
        reliability_score: number;
    }>;
    temporal: {
        daily: Array<{ date: string; runs: number; cost: number; tokens: number; success_rate: number }>;
        total_days: number;
    };
    retries: {
        avg_retries_per_run: number;
        total_retry_cost: number;
        distribution: Record<string, number>;
        top_failure_agents: Record<string, number>;
    };
    tools: {
        tools: Array<{ name: string; calls: number; successes: number; failures: number; success_rate: number }>;
        total_calls: number;
        unique_tools: number;
    };
    sources: {
        top_sources: Array<{ domain: string; hits: number; success_context: number; failure_context: number }>;
        total_urls: number;
        unique_domains: number;
    };
    token_quality: {
        successful_tokens: number;
        failed_tokens: number;
        retry_tokens: number;
        total_input: number;
        total_output: number;
        io_ratio: number;
        efficiency_pct: number;
        waste_pct: number;
    };
    insights: string[];
    by_agent: any;
    by_day: any;
}

interface StatsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

type TabId = 'overview' | 'agents' | 'tools' | 'insights';

const CHART_COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#60a5fa', '#f472b6'];

const TABS: { id: TabId; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'agents', label: 'Agents', icon: Users },
    { id: 'tools', label: 'Tools', icon: Wrench },
    { id: 'insights', label: 'Insights', icon: Lightbulb },
];

export const StatsModal: React.FC<StatsModalProps> = ({ isOpen, onClose }) => {
    const [metrics, setMetrics] = useState<FleetMetrics | null>(null);
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [activeTab, setActiveTab] = useState<TabId>('overview');
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    // Theme-aware chart colors
    const chartTextColor = isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)';
    const chartGridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
    const tooltipBg = isDark ? 'rgba(0,0,0,0.9)' : 'rgba(255,255,255,0.95)';
    const tooltipBorder = isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)';
    const tooltipTextColor = isDark ? '#fff' : '#000';

    // Dynamic container styles based on theme
    const containerClass = isDark
        ? "p-4 rounded-xl border border-border/50 bg-muted/30"
        : "p-4 rounded-xl border border-slate-200 bg-white shadow-sm";

    const summaryCardClass = isDark
        ? "p-4 rounded-xl border border-border/50 bg-muted/30 text-center"
        : "p-4 rounded-xl border border-slate-200 bg-white shadow-sm text-center";

    const fetchMetrics = async (force = false) => {
        const setter = force ? setRefreshing : setLoading;
        setter(true);
        try {
            const endpoint = force ? '/metrics/refresh' : '/metrics/dashboard';
            const method = force ? 'POST' : 'GET';
            const res = await fetch(`${API_BASE}${endpoint} `, { method });
            if (res.ok) {
                const data = await res.json();
                setMetrics(data);
            }
        } catch (e) {
            console.error('Failed to fetch metrics:', e);
        } finally {
            setter(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchMetrics();
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const dailyChartData = metrics?.temporal?.daily?.slice(0, 14).reverse() || [];
    const agentData = metrics?.agents
        ? Object.entries(metrics.agents)
            .map(([name, data]) => ({ name: name.replace('Agent', ''), ...data }))
            .sort((a, b) => b.calls - a.calls)
        : [];

    const outcomeData = metrics?.totals?.outcomes
        ? [
            { name: 'Success', value: metrics.totals.outcomes.success, color: '#34d399' },
            { name: 'Partial', value: metrics.totals.outcomes.partial, color: '#fbbf24' },
            { name: 'Failed', value: metrics.totals.outcomes.failed, color: '#f87171' },
            { name: 'Aborted', value: metrics.totals.outcomes.aborted, color: '#94a3b8' },
        ].filter(d => d.value > 0)
        : [];

    return (
        <div className={cn(
            "fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md animate-in fade-in duration-200",
            isDark ? "bg-black/70" : "bg-white/70"
        )}>
            <div className={cn(
                "w-[calc(100vw-40px)] h-[calc(100vh-40px)] overflow-hidden rounded-2xl shadow-2xl animate-in slide-in-from-bottom-4 duration-300",
                isDark ? "bg-background/98 border border-border/50 backdrop-blur-xl" : "bg-slate-50/95 border border-slate-200 backdrop-blur-xl"
            )}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 bg-gradient-to-r from-cyan-500/10 to-violet-500/10">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-gradient-to-br from-cyan-500 to-violet-500">
                            <LayoutDashboard className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-foreground">Agentic Telemetry</h2>
                            <p className="text-xs text-muted-foreground">
                                {metrics?.totals?.total_runs || 0} runs • {metrics?.temporal?.total_days || 0} days of data
                            </p>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg">
                        {TABS.map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={cn(
                                    "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                                    activeTab === tab.id
                                        ? "bg-background text-foreground shadow-sm"
                                        : "text-muted-foreground hover:text-foreground"
                                )}
                            >
                                <tab.icon className="w-4 h-4" />
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => fetchMetrics(true)}
                            disabled={refreshing}
                            className="p-2 hover:bg-muted rounded-lg transition-colors"
                        >
                            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
                        </button>
                        <button onClick={onClose} className="p-2 hover:bg-muted rounded-lg transition-colors">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto h-[calc(100%-80px)]">
                    {loading ? (
                        <div className="flex items-center justify-center h-64">
                            <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : metrics ? (
                        <>
                            {/* OVERVIEW TAB */}
                            {activeTab === 'overview' && (
                                <div className="space-y-6">
                                    {/* KPI Row 1 - Core Metrics */}
                                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                                        <KPICard icon={TrendingUp} label="Total Runs" value={metrics.totals.total_runs.toString()} color="from-cyan-500 to-blue-500" isDark={isDark} />
                                        <KPICard icon={Target} label="Success Rate" value={`${metrics.totals.success_rate}% `} color="from-green-500 to-emerald-500" isDark={isDark} />
                                        <KPICard icon={DollarSign} label="Total Cost" value={`$${metrics.totals.total_cost.toFixed(2)} `} color="from-amber-500 to-orange-500" isDark={isDark} />
                                        <KPICard icon={Zap} label="Total Tokens" value={formatNumber(metrics.totals.total_tokens)} color="from-violet-500 to-purple-500" isDark={isDark} />
                                        <KPICard icon={Clock} label="Avg Duration" value={`${metrics.totals.avg_duration_sec.toFixed(1)} s`} color="from-pink-500 to-rose-500" isDark={isDark} />
                                        <KPICard icon={Activity} label="P95 Duration" value={`${metrics.totals.p95_duration_sec.toFixed(1)} s`} color="from-slate-500 to-slate-600" isDark={isDark} />
                                    </div>

                                    {/* Charts Row 1 */}
                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                        {/* Usage Trend */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 text-foreground">Usage Over Time</h3>
                                            <div className="h-52">
                                                {dailyChartData.length > 0 ? (
                                                    <ResponsiveContainer width="100%" height="100%">
                                                        <AreaChart data={dailyChartData}>
                                                            <defs>
                                                                <linearGradient id="colorRuns" x1="0" y1="0" x2="0" y2="1">
                                                                    <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.3} />
                                                                    <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                                                                </linearGradient>
                                                            </defs>
                                                            <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                                                            <XAxis dataKey="date" stroke={chartTextColor} fontSize={10} tickFormatter={d => d?.slice(5) || ''} />
                                                            <YAxis stroke={chartTextColor} fontSize={11} />
                                                            <Tooltip contentStyle={{ background: tooltipBg, border: tooltipBorder, borderRadius: '8px', color: tooltipTextColor }} />
                                                            <Area type="monotone" dataKey="runs" stroke="#a78bfa" fillOpacity={1} fill="url(#colorRuns)" strokeWidth={2} />
                                                        </AreaChart>
                                                    </ResponsiveContainer>
                                                ) : (
                                                    <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                                                        No temporal data available yet
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Agent Breakdown Bar Chart */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 text-foreground">Agent Breakdown</h3>
                                            <div className="h-52">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <BarChart data={agentData.slice(0, 6)} layout="vertical">
                                                        <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                                                        <XAxis type="number" stroke={chartTextColor} fontSize={11} />
                                                        <YAxis dataKey="name" type="category" stroke={chartTextColor} fontSize={11} width={80} />
                                                        <Tooltip contentStyle={{ background: tooltipBg, border: tooltipBorder, borderRadius: '8px', color: tooltipTextColor }} />
                                                        <Bar dataKey="calls" fill="#22d3ee" radius={[0, 4, 4, 0]} />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Charts Row 2 */}
                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                        {/* Outcome Distribution */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 text-foreground">Outcome Distribution</h3>
                                            <div className="h-52 flex items-center">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <PieChart>
                                                        <Pie
                                                            data={outcomeData}
                                                            cx="35%"
                                                            cy="50%"
                                                            innerRadius={40}
                                                            outerRadius={65}
                                                            paddingAngle={2}
                                                            dataKey="value"
                                                        >
                                                            {outcomeData.map((entry, index) => (
                                                                <Cell key={index} fill={entry.color} />
                                                            ))}
                                                        </Pie>
                                                        <Tooltip contentStyle={{ background: tooltipBg, border: tooltipBorder, borderRadius: '8px', color: tooltipTextColor }} />
                                                        <Legend layout="vertical" align="right" verticalAlign="middle" wrapperStyle={{ fontSize: '12px' }} />
                                                    </PieChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>

                                        {/* Token Distribution Pie Chart */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 text-foreground">Token Distribution by Agent</h3>
                                            <div className="h-52 flex items-center justify-center">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <PieChart>
                                                        <Pie
                                                            data={agentData.filter(a => (a.avg_tokens * a.calls) > 0).slice(0, 5).map(a => ({ name: a.name, value: a.avg_tokens * a.calls }))}
                                                            cx="35%"
                                                            cy="50%"
                                                            innerRadius={40}
                                                            outerRadius={65}
                                                            paddingAngle={2}
                                                            dataKey="value"
                                                        >
                                                            {agentData.slice(0, 5).map((_, index) => (
                                                                <Cell key={`cell - ${index} `} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                                            ))}
                                                        </Pie>
                                                        <Tooltip contentStyle={{ background: tooltipBg, border: tooltipBorder, borderRadius: '8px', color: tooltipTextColor }} formatter={(value: number) => formatNumber(value)} />
                                                        <Legend layout="vertical" align="right" verticalAlign="middle" wrapperStyle={{ fontSize: '11px' }} />
                                                    </PieChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* AGENTS TAB */}
                            {activeTab === 'agents' && (
                                <div className="space-y-6">
                                    <div className={cn("rounded-xl border overflow-hidden", isDark ? "border-border/50" : "border-slate-200 shadow-sm")}>
                                        <table className="w-full text-sm">
                                            <thead className="bg-muted/50">
                                                <tr>
                                                    <th className="text-left px-4 py-3 font-semibold">Agent</th>
                                                    <th className="text-right px-4 py-3 font-semibold">Calls</th>
                                                    <th className="text-right px-4 py-3 font-semibold">Success</th>
                                                    <th className="text-right px-4 py-3 font-semibold">Retries</th>
                                                    <th className="text-right px-4 py-3 font-semibold">Avg Tokens</th>
                                                    <th className="text-right px-4 py-3 font-semibold">Total Cost</th>
                                                    <th className="text-right px-4 py-3 font-semibold">Reliability</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {agentData.map((agent, idx) => (
                                                    <tr key={agent.name} className={idx % 2 === 0 ? 'bg-muted/20' : ''}>
                                                        <td className="px-4 py-3 font-medium">{agent.name}</td>
                                                        <td className="text-right px-4 py-3">{agent.calls}</td>
                                                        <td className="text-right px-4 py-3">
                                                            <span className={cn(
                                                                agent.success_rate >= 90 ? 'text-green-400' :
                                                                    agent.success_rate >= 70 ? 'text-amber-400' : 'text-red-400'
                                                            )}>
                                                                {agent.success_rate}%
                                                            </span>
                                                        </td>
                                                        <td className="text-right px-4 py-3 text-muted-foreground">{agent.retry_rate}%</td>
                                                        <td className="text-right px-4 py-3">{formatNumber(agent.avg_tokens)}</td>
                                                        <td className="text-right px-4 py-3">${agent.total_cost.toFixed(4)}</td>
                                                        <td className="text-right px-4 py-3">
                                                            <div className="flex items-center justify-end gap-2">
                                                                <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                                                                    <div
                                                                        className={cn(
                                                                            "h-full rounded-full",
                                                                            agent.reliability_score >= 90 ? 'bg-green-500' :
                                                                                agent.reliability_score >= 70 ? 'bg-amber-500' : 'bg-red-500'
                                                                        )}
                                                                        style={{ width: `${agent.reliability_score}% ` }}
                                                                    />
                                                                </div>
                                                                <span className="text-xs w-8">{agent.reliability_score.toFixed(0)}</span>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>

                                    {/* Agent Cost Distribution Bar */}
                                    <div className={containerClass}>
                                        <h3 className="text-sm font-semibold mb-4 text-foreground">Cost by Agent</h3>
                                        <div className="h-48">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart data={agentData} layout="vertical">
                                                    <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                                                    <XAxis type="number" stroke={chartTextColor} fontSize={11} tickFormatter={v => `$${v.toFixed(2)} `} />
                                                    <YAxis dataKey="name" type="category" stroke={chartTextColor} fontSize={11} width={100} />
                                                    <Tooltip contentStyle={{ background: tooltipBg, border: tooltipBorder, borderRadius: '8px', color: tooltipTextColor }} />
                                                    <Bar dataKey="total_cost" fill="#22d3ee" radius={[0, 4, 4, 0]} />
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>
                                </div>
                            )}
                            {/* TOOLS TAB */}
                            {activeTab === 'tools' && (
                                <div className="space-y-6">
                                    {/* Summary Cards */}
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div className={summaryCardClass}>
                                            <p className="text-2xl font-bold text-cyan-400">{metrics.tools?.total_calls || 0}</p>
                                            <p className="text-xs text-muted-foreground uppercase">Total Tool Calls</p>
                                        </div>
                                        <div className={summaryCardClass}>
                                            <p className="text-2xl font-bold text-violet-400">{metrics.tools?.unique_tools || 0}</p>
                                            <p className="text-xs text-muted-foreground uppercase">Unique Tools</p>
                                        </div>
                                        <div className={summaryCardClass}>
                                            <p className="text-2xl font-bold text-green-400">{metrics.token_quality?.efficiency_pct || 0}%</p>
                                            <p className="text-xs text-muted-foreground uppercase">Token Efficiency</p>
                                        </div>
                                        <div className={summaryCardClass}>
                                            <p className="text-2xl font-bold text-amber-400">{metrics.sources?.unique_domains || 0}</p>
                                            <p className="text-xs text-muted-foreground uppercase">Domains Accessed</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                        {/* MCP Tool Calls Table */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                                                <Wrench className="w-4 h-4 text-cyan-400" />
                                                MCP Tool Usage
                                            </h3>
                                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                                {metrics.tools?.tools?.length ? metrics.tools.tools.map((tool, idx) => (
                                                    <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                                                        <span className="font-mono text-sm truncate flex-1">{tool.name}</span>
                                                        <div className="flex items-center gap-3 text-xs">
                                                            <span className="text-muted-foreground">{tool.calls} calls</span>
                                                            <span className={cn(
                                                                tool.success_rate >= 90 ? 'text-green-400' :
                                                                    tool.success_rate >= 70 ? 'text-amber-400' : 'text-red-400'
                                                            )}>
                                                                {tool.success_rate}%
                                                            </span>
                                                            {tool.failures > 0 && (
                                                                <span className="text-red-400">
                                                                    {tool.failures} fails
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                )) : (
                                                    <p className="text-muted-foreground text-sm">No tool calls recorded yet</p>
                                                )}
                                            </div>
                                        </div>

                                        {/* URL Sources Table */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                                                <Globe className="w-4 h-4 text-violet-400" />
                                                Internet Sources
                                            </h3>
                                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                                {metrics.sources?.top_sources?.length ? metrics.sources.top_sources.map((source, idx) => (
                                                    <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                                                        <span className="font-mono text-sm truncate flex-1">{source.domain}</span>
                                                        <div className="flex items-center gap-3 text-xs">
                                                            <span className="text-muted-foreground">{source.hits} hits</span>
                                                            {source.success_context > 0 && (
                                                                <span className="text-green-400">
                                                                    ✓ {source.success_context}
                                                                </span>
                                                            )}
                                                            {source.failure_context > 0 && (
                                                                <span className="text-red-400">
                                                                    ✗ {source.failure_context}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                )) : (
                                                    <p className="text-muted-foreground text-sm">No URL sources recorded yet</p>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Token Quality Analysis */}
                                    <div className={containerClass}>
                                        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                                            <Sparkles className="w-4 h-4 text-amber-400" />
                                            Token Quality Analysis
                                        </h3>
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                            <div className="text-center">
                                                <p className="text-lg font-bold text-green-400">{formatNumber(metrics.token_quality?.successful_tokens || 0)}</p>
                                                <p className="text-xs text-muted-foreground">Good Tokens</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-lg font-bold text-red-400">{formatNumber(metrics.token_quality?.failed_tokens || 0)}</p>
                                                <p className="text-xs text-muted-foreground">Wasted Tokens</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-lg font-bold text-amber-400">{formatNumber(metrics.token_quality?.retry_tokens || 0)}</p>
                                                <p className="text-xs text-muted-foreground">Retry Tokens</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-lg font-bold text-cyan-400">{metrics.token_quality?.io_ratio || 0}x</p>
                                                <p className="text-xs text-muted-foreground">Output/Input Ratio</p>
                                            </div>
                                        </div>
                                        <div className="mt-4">
                                            <div className="flex justify-between text-xs text-muted-foreground mb-1">
                                                <span>Token Efficiency</span>
                                                <span>{metrics.token_quality?.efficiency_pct || 0}%</span>
                                            </div>
                                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full"
                                                    style={{ width: `${metrics.token_quality?.efficiency_pct || 0}% ` }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* INSIGHTS TAB */}
                            {activeTab === 'insights' && (
                                <div className="space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        {/* Auto Insights */}
                                        <div className="p-5 rounded-xl border border-border/50 bg-gradient-to-br from-violet-500/10 to-cyan-500/10">
                                            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                                                <Lightbulb className="w-4 h-4 text-amber-400" />
                                                System Insights
                                            </h3>
                                            <div className="space-y-3">
                                                {metrics.insights?.map((insight, idx) => (
                                                    <p key={idx} className="text-sm text-foreground/90 leading-relaxed">
                                                        {insight}
                                                    </p>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Retry Stats */}
                                        <div className={containerClass}>
                                            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                                                <AlertTriangle className="w-4 h-4 text-amber-400" />
                                                Retry Analysis
                                            </h3>
                                            <div className="space-y-4">
                                                <div className="flex justify-between items-center">
                                                    <span className="text-muted-foreground">Avg Retries/Run</span>
                                                    <span className="font-mono">{metrics.retries?.avg_retries_per_run?.toFixed(2) || 0}</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-muted-foreground">Retry Cost</span>
                                                    <span className="font-mono text-amber-400">${metrics.retries?.total_retry_cost?.toFixed(4) || 0}</span>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground text-xs mb-2">Retry Distribution</p>
                                                    <div className="flex gap-2">
                                                        {Object.entries(metrics.retries?.distribution || {}).map(([key, value]) => (
                                                            <div key={key} className="flex-1 text-center p-2 rounded-lg bg-muted/50">
                                                                <p className="text-lg font-bold">{value}</p>
                                                                <p className="text-xs text-muted-foreground">{key}</p>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Top Failure Agents */}
                                    {Object.keys(metrics.retries?.top_failure_agents || {}).length > 0 && (
                                        <div className="p-5 rounded-xl border border-red-500/30 bg-red-500/5">
                                            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2 text-red-400">
                                                <XCircle className="w-4 h-4" />
                                                Top Failure Sources
                                            </h3>
                                            <div className="flex flex-wrap gap-2">
                                                {Object.entries(metrics.retries?.top_failure_agents || {}).map(([agent, count]) => (
                                                    <div key={agent} className="px-3 py-1.5 rounded-full bg-red-500/20 text-red-300 text-sm">
                                                        {agent.replace('Agent', '')}: {count} failures
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="flex items-center justify-center h-64 text-muted-foreground">
                            No metrics available
                        </div>
                    )}
                </div>
            </div>
        </div >
    );
};

interface KPICardProps {
    icon: React.FC<{ className?: string }>;
    label: string;
    value: string;
    color: string;
    isDark: boolean;
}

const KPICard: React.FC<KPICardProps> = ({ icon: Icon, label, value, color, isDark }) => (
    <div className={cn(
        "p-3 rounded-xl border group hover:scale-[1.02] transition-transform",
        isDark
            ? "border-border/50 bg-gradient-to-br from-muted/50 to-muted/20"
            : "border-slate-100 bg-white shadow-sm"
    )}>
        <div className={cn("w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center mb-2", color)}>
            <Icon className="w-4 h-4 text-white" />
        </div>
        <p className="text-xl font-bold text-foreground">{value}</p>
        <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
    </div>
);

function formatNumber(num: number): string {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)} M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)} K`;
    return num.toString();
}

export default StatsModal;
