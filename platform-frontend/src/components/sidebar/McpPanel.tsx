import React, { useEffect, useState } from 'react';
import { Box, Package, Terminal, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';

interface McpTool {
    name: string;
    description: string;
    file: string;
}

const API_BASE = 'http://localhost:8000';

export const McpPanel: React.FC = () => {
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
        <div className="flex flex-col h-full">
            {/* Top 50%: Local Tools */}
            <div className="h-[50%] border-b border-border flex flex-col">
                <div className="p-3 border-b border-border bg-charcoal-900/50">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <Terminal className="w-3 h-3" />
                        Local MCP Tools
                    </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {tools.map((tool, idx) => (
                        <div key={idx} className="p-3 bg-white/5 rounded border border-white/5 hover:border-primary/20 transition-colors group">
                            <div className="flex justify-between items-start mb-1">
                                <div className="font-mono text-xs text-primary font-bold">{tool.name}</div>
                                <div className="text-[10px] text-muted-foreground bg-primary/10 px-1.5 rounded">{tool.file}</div>
                            </div>
                            <div className="text-[10px] text-muted-foreground line-clamp-2 leading-relaxed">
                                {tool.description}
                            </div>
                        </div>
                    ))}
                    {tools.length === 0 && !loading && (
                        <div className="text-center p-4 text-xs text-muted-foreground opacity-50">
                            No local tools found
                        </div>
                    )}
                </div>
            </div>

            {/* Bottom 50%: External MCPs */}
            <div className="h-[50%] flex flex-col bg-charcoal-900/30">
                <div className="p-3 border-b border-border bg-charcoal-900/50">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <Box className="w-3 h-3" />
                        External MCP Servers
                    </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {[
                        { name: "Google Drive MCP", status: "Connected", desc: "Access Docs, Sheets, and Drive files" },
                        { name: "GitHub MCP", status: "Disconnected", desc: "Search repos, issues, and PRs" },
                        { name: "Slack MCP", status: "Connected", desc: "Read and post messages to channels" }
                    ].map((item, i) => (
                        <div key={i} className="flex items-center gap-3 p-3 rounded hover:bg-white/5 transition-colors cursor-pointer group">
                            <div className="w-8 h-8 rounded bg-white/10 flex items-center justify-center">
                                <Package className="w-4 h-4 text-muted-foreground group-hover:text-foreground" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-foreground flex items-center gap-2">
                                    {item.name}
                                    <span className={cn(
                                        "w-1.5 h-1.5 rounded-full",
                                        item.status === "Connected" ? "bg-green-500" : "bg-red-500"
                                    )} />
                                </div>
                                <div className="text-[10px] text-muted-foreground truncate">{item.desc}</div>
                            </div>
                            <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
