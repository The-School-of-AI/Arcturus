import React from 'react';
import { useAppStore } from '@/store';
import { Settings, Info, Activity, Box, Trash2, Edit3, Save, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from "@/components/ui/button";

export const CanvasInspector: React.FC = () => {
    const {
        selectedCanvasWidgetId,
        activeSurfaceId
    } = useAppStore();

    const [committing, setCommitting] = React.useState(false);

    const handleCommit = async () => {
        setCommitting(true);

        // Trigger a global save/snapshot event that widgets listen to
        const event = new CustomEvent('arcturus:commit-request', {
            detail: { surfaceId: activeSurfaceId, widgetId: selectedCanvasWidgetId }
        });
        window.dispatchEvent(event);

        // Simulate network delay for professional feel
        setTimeout(() => {
            setCommitting(false);
        }, 1500);
    };

    if (!selectedCanvasWidgetId) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                <Box className="w-12 h-12 text-muted-foreground" />
                <div className="space-y-1">
                    <h3 className="font-bold text-foreground uppercase tracking-tighter">Widget Inspector</h3>
                    <p className="text-xs text-muted-foreground max-w-[200px]">Select a widget on the canvas to view its properties and data model.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Header */}
            <div className="px-2 py-4 border-b border-border/50 bg-muted/20">
                <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-primary flex items-center gap-2">
                        <Settings className="w-3 h-3" />
                        Component Editor
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground opacity-50">
                        {selectedCanvasWidgetId}
                    </span>
                </div>
                <h2 className="text-sm font-bold truncate">
                    {selectedCanvasWidgetId.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                </h2>
            </div>

            {/* Properties Section */}
            <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6 scrollbar-hide">
                <div className="space-y-4">
                    <div className="flex items-center gap-2 pb-2 border-b border-border/30">
                        <Info className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Attributes</span>
                    </div>
                    <div className="space-y-3">
                        <div className="flex justify-between items-center text-xs">
                            <span className="text-muted-foreground">Surface ID</span>
                            <span className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded">{activeSurfaceId}</span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                            <span className="text-muted-foreground">Status</span>
                            <span className={cn(
                                "flex items-center gap-1.5 font-bold",
                                committing ? "text-amber-400" : "text-green-400"
                            )}>
                                <div className={cn(
                                    "w-1.5 h-1.5 rounded-full",
                                    committing ? "bg-amber-400 animate-bounce" : "bg-green-400 animate-pulse"
                                )} />
                                {committing ? "COMMITTING..." : "SYNCED"}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="space-y-4">
                    <div className="flex items-center gap-2 pb-2 border-b border-border/30">
                        <Activity className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Live Logs</span>
                    </div>
                    <div className="space-y-2 font-mono text-[10px]">
                        <div className="p-2 rounded bg-background/50 border border-border/30 text-muted-foreground/80 leading-relaxed">
                            <span className="text-blue-400">[WS]</span> Connected to {activeSurfaceId}<br />
                            <span className="text-green-400">[IN]</span> update_data_model received<br />
                            <span className="text-purple-400">[EV]</span> user_event(click) detected<br />
                            {committing && <><span className="text-amber-400">[SYS]</span> Preparing state checkpoint...<br /></>}
                            {!committing && <><span className="text-blue-400">[SYS]</span> Last commit at {new Date().toLocaleTimeString()}<br /></>}
                        </div>
                    </div>
                </div>

                {/* Simulated Actions */}
                <div className="pt-4 space-y-2">
                    <Button variant="outline" className="w-full justify-start gap-2 h-9 text-xs border-border/40 hover:bg-muted">
                        <Edit3 className="w-3.5 h-3.5" /> Rename Widget
                    </Button>
                    <Button variant="outline" className="w-full justify-start gap-2 h-9 text-xs border-border/40 hover:bg-muted text-red-400 hover:text-red-300">
                        <Trash2 className="w-3.5 h-3.5" /> Delete from Surface
                    </Button>
                </div>
            </div>

            {/* Footer Summary */}
            <div className="px-2 py-4 mt-auto border-t border-border/30 bg-muted/5">
                <Button
                    onClick={handleCommit}
                    disabled={committing}
                    className={cn(
                        "w-full font-bold uppercase h-10 shadow-lg transition-all",
                        committing ? "bg-muted text-muted-foreground" : "bg-primary text-primary-inventory shadow-primary/10"
                    )}
                >
                    {committing ? <RefreshCw className="w-3.5 h-3.5 mr-2 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-2" />}
                    {committing ? "Saving Block..." : "Commit Changes"}
                </Button>
            </div>
        </div>
    );
};
