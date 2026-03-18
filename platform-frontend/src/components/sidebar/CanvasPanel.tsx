import React, { useEffect, useState } from 'react';
import { Layout, Monitor, Activity, Plus, RefreshCw, Layers, LineChart as LineChartIcon, Code, Map as MapIcon, Edit3, Table, FileText, Terminal, Gauge, Image, Braces, CheckSquare, GitBranch, Share2, Loader } from 'lucide-react';
import { IconLayoutKanban } from '@tabler/icons-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import { Button } from "@/components/ui/button";
import { API_BASE } from '@/lib/api';
import axios from 'axios';

export const CanvasPanel: React.FC = () => {
    const {
        canvasSurfaces,
        activeSurfaceId,
        fetchCanvasSurfaces,
        setActiveSurfaceId,
        selectCanvasWidget
    } = useAppStore((state: any) => state);

    const [loading, setLoading] = useState(false);
    const [latency, setLatency] = useState<number | null>(null);
    const [testing, setTesting] = useState(false);

    const spawnWidget = async (componentType: string, label: string) => {
        const spawnId = `${componentType.toLowerCase()}_${Math.random().toString(36).substr(2, 5)}`;

        let props: any = {};

        if (componentType === 'LineChart') {
            const now = new Date();
            const data = [];
            for (let i = 0; i < 7; i++) {
                const hour = new Date(now.getTime() - (6 - i) * 3600000);
                data.push({
                    time: `${hour.getHours()}:00`,
                    cpu: Math.floor(Math.random() * 40) + 20,
                    mem: Math.floor(Math.random() * 30) + 40,
                    latency: Math.floor(Math.random() * 100) + 20
                });
            }

            props = {
                title: "Live Resource Analytics",
                xKey: "time",
                data,
                lines: [
                    { key: 'cpu', color: '#60a5fa', name: 'CPU (%)' },
                    { key: 'mem', color: '#fb7185', name: 'Memory (%)' },
                    { key: 'latency', color: '#34d399', name: 'Latency (ms)' }
                ]
            };
        } else if (componentType === 'Kanban') {
            props = {
                title: `New ${label}`,
                columns: [
                    { id: 'todo', title: 'To Do' },
                    { id: 'in_progress', title: 'In Progress' },
                    { id: 'done', title: 'Done' }
                ],
                initialTasks: [
                    { id: 'task_1', content: 'Design system architecture', columnId: 'todo' },
                    { id: 'task_2', content: 'Implement API endpoints', columnId: 'in_progress' },
                    { id: 'task_3', content: 'Write unit tests', columnId: 'todo' },
                ]
            };
        } else if (componentType === 'Map') {
            props = {
                title: `New ${label}`,
                center: [51.505, -0.09] as [number, number],
                zoom: 13,
                markers: [
                    { position: [51.505, -0.09] as [number, number], title: 'HQ', popup: 'Headquarters' }
                ]
            };
        } else if (componentType === 'Whiteboard') {
            props = {
                title: `New ${label}`,
                elements: [],
                appState: { theme: 'dark' }
            };
        } else if (componentType === 'DataTable') {
            props = {
                title: 'Agent Results',
                columns: [
                    { key: 'name', label: 'Name' },
                    { key: 'status', label: 'Status' },
                    { key: 'score', label: 'Score' },
                    { key: 'time', label: 'Time' },
                ],
                rows: [
                    { name: 'Task Alpha', status: 'Complete', score: 94, time: '2.3s' },
                    { name: 'Task Beta', status: 'Running', score: 78, time: '5.1s' },
                    { name: 'Task Gamma', status: 'Pending', score: 0, time: '-' },
                ]
            };
        } else if (componentType === 'Markdown') {
            props = {
                title: 'Agent Report',
                content: '## Analysis Summary\n\nThe agent completed **3 tasks** across 2 surfaces.\n\n- Task 1: Data collection ✅\n- Task 2: Processing ✅\n- Task 3: Report generation ⏳\n\n> Results are preliminary and subject to verification.\n\n| Metric | Value |\n|--------|-------|\n| Accuracy | 94.2% |\n| Latency | 120ms |'
            };
        } else if (componentType === 'Terminal') {
            props = {
                title: 'Agent Logs',
                lines: [
                    '$ arcturus agent start --mode=research',
                    '✓ Agent initialized (model: gemma3:4b)',
                    '✓ Memory context loaded (42 entries)',
                    '# Searching knowledge base...',
                    '> Found 7 relevant documents',
                    '> Processing query: "system architecture"',
                    '✓ Response generated in 1.2s',
                ]
            };
        } else if (componentType === 'MetricCard') {
            props = {
                title: 'System Metrics',
                metrics: [
                    { label: 'Uptime', value: '99.9%', delta: '+0.1%', deltaType: 'positive' },
                    { label: 'Latency', value: '42ms', delta: '-8ms', deltaType: 'positive' },
                    { label: 'Requests', value: '12.4K', delta: '+2.1K', deltaType: 'positive' },
                    { label: 'Errors', value: '3', delta: '+1', deltaType: 'negative' },
                ]
            };
        } else if (componentType === 'ImageViewer') {
            props = {
                title: 'Screenshots',
                layout: 'carousel',
                images: [
                    { src: 'https://picsum.photos/seed/arc1/600/400', caption: 'Dashboard Overview' },
                    { src: 'https://picsum.photos/seed/arc2/600/400', caption: 'Agent Flow' },
                ]
            };
        } else if (componentType === 'JSONViewer') {
            props = {
                title: 'API Response',
                data: {
                    status: 'success',
                    agent: { id: 'agent-001', model: 'gemma3:4b', mode: 'research' },
                    results: [
                        { query: 'architecture', matches: 7, confidence: 0.94 },
                        { query: 'deployment', matches: 3, confidence: 0.87 },
                    ],
                    metadata: { latency_ms: 42, tokens_used: 1250 }
                }
            };
        } else if (componentType === 'TodoList') {
            props = {
                title: 'Sprint Tasks',
                items: [
                    { id: 't1', text: 'Set up agent pipeline', done: true },
                    { id: 't2', text: 'Configure memory store', done: true },
                    { id: 't3', text: 'Implement RAG indexing', done: false },
                    { id: 't4', text: 'Add WebSocket sync', done: false },
                    { id: 't5', text: 'Deploy to production', done: false },
                ]
            };
        } else if (componentType === 'Progress') {
            props = {
                title: 'Agent Pipeline',
                steps: [
                    { label: 'Input Parsing', status: 'done', detail: 'Tokenized 250 words' },
                    { label: 'Memory Retrieval', status: 'done', detail: '7 matches found' },
                    { label: 'Reasoning', status: 'active', detail: 'Chain-of-thought in progress' },
                    { label: 'Response Generation', status: 'pending' },
                    { label: 'Quality Check', status: 'pending' },
                ]
            };
        } else if (componentType === 'FlowChart') {
            props = {
                title: 'Agent Workflow',
                nodes: [
                    { id: '1', data: { label: 'User Input' }, position: { x: 0, y: 0 }, style: { background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '8px' } },
                    { id: '2', data: { label: 'Intent Router' }, position: { x: 0, y: 100 }, style: { background: '#8b5cf6', color: '#fff', border: 'none', borderRadius: '8px' } },
                    { id: '3', data: { label: 'Memory Search' }, position: { x: -150, y: 200 }, style: { background: '#10b981', color: '#fff', border: 'none', borderRadius: '8px' } },
                    { id: '4', data: { label: 'RAG Lookup' }, position: { x: 150, y: 200 }, style: { background: '#f59e0b', color: '#fff', border: 'none', borderRadius: '8px' } },
                    { id: '5', data: { label: 'Response' }, position: { x: 0, y: 300 }, style: { background: '#ef4444', color: '#fff', border: 'none', borderRadius: '8px' } },
                ],
                edges: [
                    { id: 'e1-2', source: '1', target: '2', animated: true },
                    { id: 'e2-3', source: '2', target: '3' },
                    { id: 'e2-4', source: '2', target: '4' },
                    { id: 'e3-5', source: '3', target: '5' },
                    { id: 'e4-5', source: '4', target: '5' },
                ]
            };
        } else if (componentType === 'NetworkGraph') {
            props = {
                title: 'Knowledge Graph',
                nodes: [
                    { id: 1, label: 'Arcturus', color: '#3b82f6' },
                    { id: 2, label: 'Canvas', color: '#10b981' },
                    { id: 3, label: 'Echo', color: '#8b5cf6' },
                    { id: 4, label: 'Memory', color: '#f59e0b' },
                    { id: 5, label: 'RAG', color: '#ef4444' },
                    { id: 6, label: 'Agent', color: '#ec4899' },
                ],
                edges: [
                    { from: 1, to: 2, label: 'renders' },
                    { from: 1, to: 3, label: 'speaks' },
                    { from: 1, to: 4, label: 'remembers' },
                    { from: 6, to: 4, label: 'queries' },
                    { from: 6, to: 5, label: 'searches' },
                    { from: 6, to: 2, label: 'pushes UI' },
                ]
            };
        }

        if (componentType === 'MonacoEditor') {
            props = {
                title: "Research Agent Loop",
                code: "// Arcturus Research Agent Runtime\nasync function conductResearch(topic) {\n    console.log(`🚀 Task: Researching \"${topic}\"...`);\n    \n    // 1. (Optional) Sync Memory to ensure latest chat context is available\n    await Arcturus.ki.sync();\n\n    // 2. Unified Search (Memory + Documents)\n    const results = await Arcturus.search(topic);\n    \n    if (results.snippets.length > 0) {\n        console.log(`✅ Found ${results.snippets.length} document snippets.`);\n        // Find a specific stat in the text\n        const stat = results.snippets[0].content.split('.').find(s => s.toLowerCase().includes('world cup') || s.includes('trophy'));\n        if (stat) console.log(`🏆 Key Stat: ${stat.trim()}.`);\n    }\n\n    // 3. results.length works for backward compatibility, \n    // or use results.memories.length for specific episodic matches\n    console.log(`🧠 Knowledge matches: ${results.length}`);\n\n    // 4. Update Surface\n    Surface.updateMetadata({\n        status: 'Active Intelligence',\n        topic: topic,\n        lastAnalysis: new Date().toLocaleTimeString()\n    });\n}\n\n// Try 'cricket' or 'Monaco'!\nawait conductResearch('Cricketers and match details IPL or ICC or WorldCup');",
                language: "javascript",
                theme: "vs-dark"
            };
        }

        try {
            // Fetch current components so we don't overwrite everything
            const currentRes = await axios.get(`${API_BASE}/canvas/state/${activeSurfaceId}`);
            const currentComponents = currentRes.data.components || [];

            const newComponent = {
                id: spawnId,
                component: componentType,
                props,
                children: []
            };

            await axios.post(`${API_BASE}/canvas/test-update/${activeSurfaceId}`, {
                components: [...currentComponents, newComponent]
            });
            selectCanvasWidget(spawnId);
        } catch (err) {
            console.error("Failed to spawn widget:", err);
        }
    };

    useEffect(() => {
        setLoading(true);
        fetchCanvasSurfaces().finally(() => setLoading(false));
    }, [fetchCanvasSurfaces]);

    const runConnectivityTest = async () => {
        setTesting(true);
        const start = performance.now();
        try {
            await axios.get(`${API_BASE}/canvas/state/${activeSurfaceId}`);
            setLatency(Math.round(performance.now() - start));
        } catch (e) {
            setLatency(999);
        } finally {
            setTesting(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header / Search */}
            <div className="p-4 border-b border-border/50 bg-muted/20 shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                        <Layers className="w-3.5 h-3.5 text-primary" />
                        Surface Explorer
                    </h2>
                    <Button variant="ghost" size="icon" className="h-6 w-6 rounded-md hover:bg-primary/10 hover:text-primary transition-colors" onClick={() => fetchCanvasSurfaces()}>
                        <Plus className="w-3.5 h-3.5" />
                    </Button>
                </div>

                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1 scrollbar-hide">
                    {loading ? (
                        <div className="flex items-center justify-center p-8">
                            <RefreshCw className="w-5 h-5 animate-spin text-muted-foreground/30" />
                        </div>
                    ) : (
                        canvasSurfaces.map((surface: any) => (
                            <div
                                key={surface.id}
                                onClick={() => setActiveSurfaceId(surface.id)}
                                className={cn(
                                    "group p-3 rounded-lg border transition-all cursor-pointer",
                                    activeSurfaceId === surface.id
                                        ? "border-primary/50 bg-primary/5 shadow-[0_0_10px_rgba(255,255,0,0.05)]"
                                        : "border-border/40 hover:border-border/60 bg-background/50 hover:bg-background/80"
                                )}
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <h3 className={cn(
                                        "text-[11px] font-bold truncate",
                                        activeSurfaceId === surface.id ? "text-primary" : "text-foreground"
                                    )}>
                                        {surface.title || surface.id}
                                    </h3>
                                    <Monitor className={cn(
                                        "w-3 h-3",
                                        activeSurfaceId === surface.id ? "text-primary" : "text-muted-foreground/30"
                                    )} />
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="flex items-center gap-1">
                                        <Activity className="w-2.5 h-2.5 text-muted-foreground/40" />
                                        <span className="text-2xs text-muted-foreground font-medium">{surface.componentCount || 0} Components</span>
                                    </div>
                                    <div className="text-2xs text-muted-foreground/40 font-mono">
                                        ID: {surface.id}
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Catalog Section */}
            <div className="p-4 border-b border-border/50 bg-muted/10 shrink-0">
                <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-4 flex items-center gap-2">
                    <Layout className="w-3 h-3" />
                    Widget Catalog
                </h2>
                <div className="grid grid-cols-3 gap-1.5 max-h-[280px] overflow-y-auto scrollbar-hide">
                    {([
                        { type: 'DataTable', label: 'Table', icon: Table, color: 'text-emerald-400' },
                        { type: 'Markdown', label: 'Markdown', icon: FileText, color: 'text-slate-400' },
                        { type: 'Terminal', label: 'Terminal', icon: Terminal, color: 'text-lime-400' },
                        { type: 'MetricCard', label: 'Metrics', icon: Gauge, color: 'text-rose-400' },
                        { type: 'LineChart', label: 'Chart', icon: LineChartIcon, color: 'text-orange-400' },
                        { type: 'MonacoEditor', label: 'Code', icon: Code, color: 'text-cyan-400' },
                        { type: 'Kanban', label: 'Kanban', icon: IconLayoutKanban, color: 'text-blue-400' },
                        { type: 'Map', label: 'Map', icon: MapIcon, color: 'text-green-400' },
                        { type: 'Whiteboard', label: 'Sketch', icon: Edit3, color: 'text-purple-400' },
                        { type: 'TodoList', label: 'Tasks', icon: CheckSquare, color: 'text-teal-400' },
                        { type: 'Progress', label: 'Progress', icon: Loader, color: 'text-amber-400' },
                        { type: 'FlowChart', label: 'Flow', icon: GitBranch, color: 'text-violet-400' },
                        { type: 'NetworkGraph', label: 'Network', icon: Share2, color: 'text-pink-400' },
                        { type: 'JSONViewer', label: 'JSON', icon: Braces, color: 'text-yellow-400' },
                        { type: 'ImageViewer', label: 'Images', icon: Image, color: 'text-sky-400' },
                    ] as const).map(w => (
                        <div
                            key={w.type}
                            onClick={() => spawnWidget(w.type, w.label)}
                            className="flex flex-col items-center gap-1.5 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                        >
                            <w.icon className={`w-3.5 h-3.5 ${w.color} group-hover:scale-110 transition-transform`} />
                            <span className="text-2xs uppercase font-bold tracking-tight opacity-60 group-hover:opacity-100">{w.label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Diagnostics Section */}
            <div className="p-4 mt-auto">
                <div className="p-3 rounded-xl bg-muted/20 border border-border/30 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-bold uppercase tracking-wide text-muted-foreground flex items-center gap-2">
                            <Activity className="w-3.5 h-3.5 text-blue-400" />
                            Health
                        </span>
                        {latency !== null && (
                            <div className="flex items-center gap-1.5">
                                <span className={cn(
                                    "w-1.5 h-1.5 rounded-full animate-pulse",
                                    latency < 50 ? "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]" : latency < 150 ? "bg-amber-400" : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]"
                                )} />
                                <span className={cn(
                                    "text-xs font-mono font-bold tabular-nums",
                                    latency < 50 ? "text-green-400" : latency < 150 ? "text-amber-400" : "text-red-400"
                                )}>
                                    {latency}ms
                                </span>
                            </div>
                        )}
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="w-full text-xs font-bold uppercase tracking-wide h-8 border border-border/40 hover:bg-background/80 hover:border-primary/30 transition-all group"
                        onClick={runConnectivityTest}
                        disabled={testing}
                    >
                        {testing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : "Verify Connection"}
                    </Button>
                </div>
            </div>
        </div>
    );
};
