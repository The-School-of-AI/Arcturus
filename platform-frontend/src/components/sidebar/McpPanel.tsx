import React, { useEffect, useState } from 'react';
import { Box, Package, Terminal, ExternalLink, Plus, Trash2, Globe, Command, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { useAppStore } from '@/store';
import { API_BASE } from '@/lib/api';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface McpServer {
    name: string;
    config: any;
    status: 'connected' | 'disconnected';
}

export const McpPanel: React.FC = () => {
    const {
        selectedMcpServer,
        setSelectedMcpServer,
        mcpServers: servers,
        setMcpServers: setServers,
        fetchMcpServers: fetchServers,
        isMcpAddOpen: isAddOpen,
        setIsMcpAddOpen: setIsAddOpen
    } = useAppStore();

    const [loading, setLoading] = useState(false);

    // Add Server State
    const [newServerName, setNewServerName] = useState("");
    const [newServerType, setNewServerType] = useState("stdio-pypi");
    const [newServerSource, setNewServerSource] = useState("");
    const [newServerEntry, setNewServerEntry] = useState("src/server.py");
    const [adding, setAdding] = useState(false);


    const handleAddServer = async () => {
        if (!newServerName || !newServerSource) return;
        setAdding(true);
        try {
            const config: any = {
                type: newServerType
            };

            if (newServerType === 'stdio-pypi') {
                config.command = 'uvx';
                config.args = [newServerSource]; // Package name
            } else if (newServerType === 'stdio-git') {
                config.source = newServerSource; // Git URL
                config.command = 'uv';
                config.args = ["run", newServerEntry || "src/server.py"];
            }

            await axios.post(`${API_BASE}/mcp/servers`, {
                name: newServerName.toLowerCase().replace(/\s+/g, '_'),
                config
            });
            await fetchServers();
            setIsAddOpen(false);
            setNewServerName("");
            setNewServerSource("");
            setNewServerEntry("src/server.py");
        } catch (e) {
            console.error("Failed to add server", e);
            alert("Failed to add server. Check console.");
        } finally {
            setAdding(false);
        }
    };

    const handleDelete = async (e: React.MouseEvent, name: string) => {
        e.stopPropagation();
        if (!confirm(`Delete server '${name}'?`)) return;
        try {
            await axios.delete(`${API_BASE}/mcp/servers/${name}`);
            await fetchServers();
        } catch (e) {
            console.error("Failed to delete", e);
        }
    };

    return (
        <div className="flex flex-col h-full bg-card text-foreground">
            {/* Header Content moved to Top Bar */}
            <div className="hidden">
                <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
                    <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                        <DialogHeader>
                            <DialogTitle className="text-foreground">Add New MCP Server</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-2">
                            <div className="space-y-2">
                                <Label>Server Name</Label>
                                <Input
                                    placeholder="e.g. finance"
                                    value={newServerName}
                                    onChange={e => setNewServerName(e.target.value)}
                                    className="bg-muted border-border"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Type</Label>
                                <Select value={newServerType} onValueChange={setNewServerType}>
                                    <SelectTrigger className="bg-muted border-border">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-popover border-border">
                                        <SelectItem value="stdio-pypi">PyPI Package (uvx)</SelectItem>
                                        <SelectItem value="stdio-git">GitHub Repository</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>{newServerType === 'stdio-pypi' ? 'Package Name' : 'Git URL'}</Label>
                                <Input
                                    placeholder={newServerType === 'stdio-pypi' ? "e.g. @modelcontextprotocol/server-filesystem" : "https://github.com/..."}
                                    value={newServerSource}
                                    onChange={e => setNewServerSource(e.target.value)}
                                    className="bg-muted border-border"
                                />
                            </div>

                            {newServerType === 'stdio-git' && (
                                <div className="space-y-2">
                                    <Label>Script Path (Entry Point)</Label>
                                    <Input
                                        placeholder="e.g. src/server.py"
                                        value={newServerEntry}
                                        onChange={e => setNewServerEntry(e.target.value)}
                                        className="bg-muted border-border"
                                    />
                                    <p className="text-[10px] text-muted-foreground">Relative path to the server script in the repo.</p>
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsAddOpen(false)} className="border-border text-foreground hover:bg-muted">Cancel</Button>
                            <Button onClick={handleAddServer} disabled={adding} className="bg-neon-yellow text-neutral-950 font-semibold hover:bg-neon-yellow/90">
                                {adding && <Loader2 className="w-3 h-3 mr-2 animate-spin" />}
                                Add Server
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Default "Built-in" Servers (Browser, RAG, Sandbox) handled as just servers now 
                But we might want to group them visually or just list them all.
            */}

            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-hide">
                {servers.map((server, idx) => {
                    const isSelected = selectedMcpServer === server.name;
                    // Determine Type Icon
                    let typeIcon = <Box className="w-4 h-4" />;
                    if (server.name === 'browser') typeIcon = <Globe className="w-4 h-4" />;
                    else if (server.name === 'rag') typeIcon = <Command className="w-4 h-4" />;
                    else if (server.config?.type === 'stdio-git') typeIcon = <ExternalLink className="w-4 h-4" />;
                    else if (server.config?.type === 'stdio-pypi') typeIcon = <Package className="w-4 h-4" />;

                    return (
                        <div
                            key={idx}
                            className={cn(
                                "group relative p-3 rounded-xl border transition-all duration-300 cursor-pointer overflow-hidden",
                                isSelected
                                    ? "bg-primary/10 border-primary shadow-[0_0_15px_rgba(var(--primary-rgb),0.1)]"
                                    : "bg-gradient-to-br from-card to-muted/20 border-border/50 hover:border-white/20 hover:bg-muted/30"
                            )}
                            onClick={() => setSelectedMcpServer(server.name)}
                        >
                            <div className="flex justify-between items-center gap-3">
                                <div className={cn(
                                    "w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
                                    isSelected ? "bg-primary text-primary-inventory" : "bg-muted/50 text-muted-foreground"
                                )}>
                                    {typeIcon}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className={cn(
                                            "text-xs font-bold uppercase tracking-wide",
                                            isSelected ? "text-primary" : "text-foreground"
                                        )}>
                                            {server.name}
                                        </span>
                                        <span className={cn(
                                            "w-1.5 h-1.5 rounded-full",
                                            server.status === 'connected' ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]" : "bg-red-500"
                                        )} title={server.status} />
                                    </div>
                                    <div className="text-[10px] text-muted-foreground truncate opacity-70">
                                        {server.config?.type || 'local'} • {server.config?.args?.[0] || 'managed'}
                                    </div>
                                </div>

                                {server.config?.type && server.config.type !== 'local-script' && (
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive/20 hover:text-destructive"
                                        onClick={(e) => handleDelete(e, server.name)}
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </Button>
                                )}
                            </div>
                        </div>
                    );
                })}

                {servers.length === 0 && !loading && (
                    <div className="text-center p-8 text-xs text-muted-foreground opacity-50">
                        No servers found
                    </div>
                )}
            </div>
        </div>
    );
};
