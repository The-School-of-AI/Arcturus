import React, { useEffect, useState } from 'react';
import { Box, Package, Terminal, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';

interface McpTool {
    name: string;
    description: string;
    file: string;
}

export const McpPanel: React.FC = () => {
    const { setSelectedMcpServer } = useAppStore();
    const [tools, setTools] = useState<McpTool[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchTools = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/mcp/tools`);
            setTools(res.data.tools);
        } catch (e) {
            console.error("Failed to fetch MCP tools", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTools();
    }, []);

    return (
        <div className="flex flex-col h-full bg-card text-foreground">
            {/* Header - Matches Remme Style */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-card/50 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-neon-yellow/10 rounded-lg">
                        <Box className="w-5 h-5 text-neon-yellow" />
                    </div>
                    <div>
                        <h2 className="font-semibold text-sm tracking-tight text-foreground uppercase">MCP Browser</h2>
                        <p className="text-[10px] text-neon-yellow/80 font-mono tracking-widest">{tools.length} TOOLS AVAILABLE</p>
                    </div>
                </div>
            </div>

            {/* Local Tools Section */}
            <div className="border-b border-border/50">
                <div className="p-3 bg-muted/20">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                        <Terminal className="w-3 h-3" />
                        Local MCP Tools
                    </h3>
                </div>
                <div className="p-4 space-y-4 max-h-[35vh] overflow-y-auto scrollbar-hide">
                    {tools.map((tool, idx) => (
                        <div key={idx} className={cn(
                            "group relative p-4 rounded-xl border transition-all duration-300",
                            "bg-gradient-to-br from-card to-muted/20",
                            "hover:shadow-md border-border/50 hover:border-white/20"
                        )}>
                            <div className="flex justify-between items-start mb-2">
                                <div className="font-mono text-xs text-foreground font-bold">{tool.name}</div>
                                <div className="text-[9px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{tool.file}</div>
                            </div>
                            <div className="text-[11px] text-muted-foreground line-clamp-2 group-hover:line-clamp-none leading-relaxed transition-all duration-300">
                                {tool.description}
                            </div>
                        </div>
                    ))}
                    {tools.length === 0 && !loading && (
                        <div className="text-center p-8 text-xs text-muted-foreground opacity-50">
                            No local tools found
                        </div>
                    )}
                </div>
            </div>

            {/* External MCPs Section */}
            <div className="flex-1 flex flex-col">
                <div className="p-3 bg-muted/20 border-b border-border/50">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                        <Package className="w-3 h-3" />
                        External MCP Servers
                    </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                    {[
                        { name: "Alpha Vantage MCP", status: "Connected", desc: "Stock market and financial data", id: "alphavantage" },
                        { name: "Google Drive MCP", status: "Connected", desc: "Access Docs, Sheets, and Drive files", id: "gdrive" },
                        { name: "GitHub MCP", status: "Disconnected", desc: "Search repos, issues, and PRs", id: "github" },
                        { name: "Slack MCP", status: "Connected", desc: "Read and post messages to channels", id: "slack" }
                    ].map((item, i) => (
                        <div
                            key={i}
                            className={cn(
                                "flex items-center gap-3 p-4 rounded-xl border transition-all duration-300 cursor-pointer group",
                                "bg-gradient-to-br from-card to-muted/20",
                                "hover:shadow-md border-border/50 hover:border-white/20"
                            )}
                            onClick={() => item.id === 'alphavantage' && setSelectedMcpServer(item.id)}
                        >
                            <div className="w-10 h-10 rounded-lg bg-muted/50 flex items-center justify-center">
                                <Package className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-[13px] font-medium text-foreground flex items-center gap-2">
                                    {item.name}
                                    <span className={cn(
                                        "w-2 h-2 rounded-full",
                                        item.status === "Connected" ? "bg-green-500" : "bg-red-500"
                                    )} />
                                </div>
                                <div className="text-[10px] text-muted-foreground truncate mt-0.5">{item.desc}</div>
                            </div>
                            <ExternalLink className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
