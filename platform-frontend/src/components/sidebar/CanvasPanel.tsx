import React, { useEffect, useState } from 'react';
import { Layout, Monitor, Activity, Plus, RefreshCw, Layers, Map as MapIcon, Kanban as KanbanIcon, Edit3 } from 'lucide-react';
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

        try {
            await axios.post(`${API_BASE}/canvas/test-update/${activeSurfaceId}`, {
                id: spawnId,
                component: componentType,
                props: {
                    title: `New ${label}`,
                    description: `Instantiated from Catalog`
                }
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
                        onClick={() => spawnWidget('KanbanWidget', 'Kanban')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <KanbanIcon className="w-4 h-4 text-blue-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Kanban</span>
                    </div>
                    <div
                        onClick={() => spawnWidget('MapWidget', 'Map')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <MapIcon className="w-4 h-4 text-green-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Map</span>
                    </div>
                    <div
                        onClick={() => spawnWidget('WhiteboardWidget', 'Sketch')}
                        className="flex flex-col items-center gap-2 p-2 rounded-lg bg-background/40 border border-border/30 hover:border-border/60 transition-all cursor-pointer group hover:translate-y-[-1px] hover:bg-primary/5"
                    >
                        <Edit3 className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
                        <span className="text-[8px] uppercase font-bold tracking-tighter opacity-60 group-hover:opacity-100">Sketch</span>
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
