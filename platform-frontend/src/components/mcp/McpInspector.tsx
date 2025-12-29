import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { Settings2, CheckCircle2, ChevronRight, Info } from 'lucide-react';
import axios from 'axios';
import { cn } from '@/lib/utils';
import { API_BASE } from '@/lib/api';

interface Tool {
    name: string;
    description: string;
    inputSchema: any;
}

export const McpInspector: React.FC = () => {
    const { selectedMcpServer, mcpToolStates, toggleMcpTool, setMcpToolStates } = useAppStore();
    const [tools, setTools] = useState<Tool[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!selectedMcpServer) return;

        const fetchTools = async () => {
            setLoading(true);
            try {
                const res = await axios.get(`${API_BASE}/mcp/connected_tools`);
                const serverTools = res.data.servers[selectedMcpServer] || [];
                setTools(serverTools);

                // Initialize state if not present in store
                const currentStates = mcpToolStates[selectedMcpServer] || {};
                const missingKeys = serverTools.some((t: Tool) => currentStates[t.name] === undefined);

                if (missingKeys || Object.keys(currentStates).length === 0) {
                    const status: Record<string, boolean> = { ...currentStates };
                    serverTools.forEach((t: Tool) => {
                        if (status[t.name] === undefined) {
                            status[t.name] = true; // Default to enabled
                        }
                    });
                    setMcpToolStates(selectedMcpServer, status);
                }

            } catch (e) {
                console.error("Failed to fetch mcp tools", e);
            } finally {
                setLoading(false);
            }
        };

        fetchTools();
    }, [selectedMcpServer]); // Don't depend on toolStates to avoid loops

    if (!selectedMcpServer) {
        return (
            <div className="h-full flex items-center justify-center p-8 text-center bg-background">
                <div className="space-y-3">
                    <Info className="w-10 h-10 text-muted-foreground mx-auto opacity-20" />
                    <p className="text-sm text-muted-foreground">Select an MCP server from the library to configure tools</p>
                </div>
            </div>
        );
    }

    const enabledTools = mcpToolStates[selectedMcpServer] || {};

    const toggleTool = (name: string) => {
        toggleMcpTool(selectedMcpServer, name);
    };

    const isAllEnabled = tools.length > 0 && tools.every(t => enabledTools[t.name]);

    const toggleAll = () => {
        const newState = !isAllEnabled;
        const nextStatus: Record<string, boolean> = {};
        tools.forEach(t => {
            nextStatus[t.name] = newState;
        });
        setMcpToolStates(selectedMcpServer, nextStatus);
    };

    return (
        <div className="flex flex-col h-full bg-background">
            <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Settings2 className="w-4 h-4 text-primary" />
                        <h2 className="text-sm font-bold uppercase tracking-wider">{selectedMcpServer.replace('_', ' ')} Inspector</h2>
                    </div>
                    <p className="text-[10px] text-muted-foreground">Configure and enable/disable specific capabilities</p>
                </div>

                {tools.length > 0 && (
                    <div
                        onClick={toggleAll}
                        className="flex items-center gap-2 px-2 py-1 rounded bg-white/5 border border-white/10 hover:bg-white/10 cursor-pointer transition-colors"
                    >
                        <span className="text-[10px] uppercase font-bold tracking-tight text-muted-foreground">
                            {isAllEnabled ? 'Disable All' : 'Enable All'}
                        </span>
                        <div className={cn(
                            "w-6 h-3 rounded-full relative transition-colors",
                            isAllEnabled ? "bg-primary" : "bg-white/20"
                        )}>
                            <div className={cn(
                                "absolute top-0.5 w-2 h-2 rounded-full bg-white transition-all",
                                isAllEnabled ? "right-0.5" : "left-0.5"
                            )} />
                        </div>
                    </div>
                )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {loading ? (
                    <div className="flex items-center justify-center h-40">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                ) : tools.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-10">No tools found for this server</p>
                ) : (
                    tools.map((tool, idx) => (
                        <div
                            key={idx}
                            onClick={() => toggleTool(tool.name)}
                            className={cn(
                                "group p-3 rounded-lg border transition-all cursor-pointer",
                                enabledTools[tool.name]
                                    ? "bg-primary/5 border-primary/20 hover:border-primary/40"
                                    : "bg-background/40 border-border opacity-60 hover:opacity-80"
                            )}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1">
                                    <h4 className="font-mono text-xs font-bold text-primary mb-1 flex items-center gap-2">
                                        {tool.name}
                                        {enabledTools[tool.name] && <CheckCircle2 className="w-3 h-3" />}
                                    </h4>
                                    <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2">
                                        {tool.description}
                                    </p>
                                </div>
                                <div className={cn(
                                    "w-4 h-4 rounded border flex items-center justify-center transition-colors",
                                    enabledTools[tool.name] ? "bg-primary border-primary" : "border-muted-foreground/30"
                                )}>
                                    {enabledTools[tool.name] && <div className="w-1.5 h-1.5 bg-black rounded-full" />}
                                </div>
                            </div>

                            {enabledTools[tool.name] && tool.inputSchema?.properties && (
                                <div className="mt-2 pt-2 border-t border-primary/10">
                                    <div className="text-[9px] text-muted-foreground uppercase font-bold tracking-tighter mb-1">Params:</div>
                                    <div className="flex flex-wrap gap-1">
                                        {Object.keys(tool.inputSchema.properties).map(prop => (
                                            <span key={prop} className="text-[8px] bg-white/5 px-1.5 py-0.5 rounded font-mono">
                                                {prop}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
