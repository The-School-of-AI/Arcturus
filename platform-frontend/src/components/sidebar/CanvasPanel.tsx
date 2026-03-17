import React, { useEffect, useState } from 'react';
import { Layout, Monitor, Activity, Plus, RefreshCw, Layers, LineChart as LineChartIcon, Code, Map as MapIcon, Edit3 } from 'lucide-react';
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
                    <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
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
                                        ? "border-neon-yellow/50 bg-neon-yellow/5 shadow-[0_0_10px_rgba(255,255,0,0.05)]"
                                        : "border-border/40 hover:border-border/60 bg-background/50 hover:bg-background/80"
                                )}
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <h3 className={cn(
                                        "text-[11px] font-bold truncate",
                                        activeSurfaceId === surface.id ? "text-neon-yellow" : "text-foreground"
                                    )}>
                                        {surface.title || surface.id}
                                    </h3>
                                    <Monitor className={cn(
                                        "w-3 h-3",
                                        activeSurfaceId === surface.id ? "text-neon-yellow" : "text-muted-foreground/30"
                                    )} />
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="flex items-center gap-1">
                                        <Activity className="w-2.5 h-2.5 text-muted-foreground/40" />
                                        <span className="text-[9px] text-muted-foreground font-medium">{surface.componentCount || 0} Components</span>
                                    </div>
                                    <div className="text-[9px] text-muted-foreground/40 font-mono">
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
                <h2 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-4 flex items-center gap-2">
                    <Layout className="w-3 h-3" />
                    Widget Catalog
                </h2>
                <div className="grid grid-cols-3 gap-2">
                    <div
                        onClick={() => spawnWidget('Kanban', 'Kanban')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <IconLayoutKanban className="w-4 h-4 text-blue-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Kanban</span>
                    </div>
                    <div
                        onClick={() => spawnWidget('Map', 'Map')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <MapIcon className="w-4 h-4 text-green-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Map</span>
                    </div>
                    <div
                        onClick={() => spawnWidget('Whiteboard', 'Sketch')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <Edit3 className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Sketch</span>
                    </div>
                    <div
                        onClick={() => spawnWidget('LineChart', 'Analytics')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <LineChartIcon className="w-4 h-4 text-orange-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Analytics</span>
                    </div>
                    <div
                        onClick={() => spawnWidget('MonacoEditor', 'Code')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <Code className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Code</span>
                    </div>
                </div>
            </div>

            {/* Diagnostics Section */}
            <div className="p-4 mt-auto">
                <div className="p-3 rounded-xl bg-muted/20 border border-border/30 backdrop-blur-sm">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
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
                                    "text-[10px] font-mono font-bold tabular-nums",
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
                        className="w-full text-[10px] font-bold uppercase tracking-widest h-8 border border-border/40 hover:bg-background/80 hover:border-neon-yellow/30 transition-all group"
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
