import React from 'react';
import { Code2, Terminal, Globe, FileCode, CheckCircle2, Eye, Clock, Brain } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import Editor from "@monaco-editor/react";
import ReactMarkdown from 'react-markdown';
import DOMPurify from 'dompurify';
import { API_BASE } from '@/lib/api';

// Helper component for tabs (assuming it's a simple button for now)
const PanelTab: React.FC<{ label: string; active: boolean; onClick: () => void; icon: React.ReactNode }> = ({ label, active, onClick, icon }) => (
    <button
        onClick={onClick}
        className={cn(
            "flex items-center gap-2 px-4 py-3 text-xs font-medium border-b-2 transition-all hover:bg-accent/50",
            active
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground"
        )}
    >
        {icon}
        {label}
    </button>
);

// Sub-component for User Input to avoid Hook errors in conditional rendering
const ClarificationInput: React.FC<{ selectedNode: any; codeContent: string }> = ({ selectedNode, codeContent }) => {
    let message = "This agent requires your input to proceed.";
    try {
        const parsed = JSON.parse(codeContent);
        if (parsed.clarificationMessage) {
            message = parsed.clarificationMessage;
        }
    } catch { }

    const [inputValue, setInputValue] = React.useState('');
    const [isSubmitting, setIsSubmitting] = React.useState(false);

    const handleSubmit = async () => {
        if (!inputValue.trim()) return;
        setIsSubmitting(true);
        try {
            const runId = useAppStore.getState().currentRun?.id;
            if (runId) {
                await fetch(`${API_BASE}/runs/${runId}/input`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ input: inputValue })
                });
                setInputValue('');
            }
        } catch (e) {
            console.error("Failed to submit input:", e);
            alert("Failed to submit input: " + e);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg space-y-3 animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center gap-2 text-yellow-400 font-bold text-xs uppercase tracking-wider">
                <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                User Input Required
            </div>
            <div className="text-sm text-foreground/90 leading-relaxed font-medium">
                {message}
            </div>
            <div className="flex gap-2">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !isSubmitting && handleSubmit()}
                    placeholder="Type your response here..."
                    className="flex-1 bg-background border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-yellow-500/50 transition-colors"
                    disabled={isSubmitting}
                />
                <button
                    onClick={handleSubmit}
                    disabled={!inputValue.trim() || isSubmitting}
                    className="px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black font-semibold text-xs rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed uppercase tracking-wide"
                >
                    {isSubmitting ? 'Sending...' : 'Send'}
                </button>
            </div>
        </div>
    );
};

import { DocumentAssistant } from '../rag/DocumentAssistant';

export const WorkspacePanel: React.FC = () => {
    const {
        codeContent, webUrl, logs, selectedNodeId, nodes, sidebarTab,
        flowData, selectedExplorerNodeId, currentRun
    } = useAppStore();
    const [activeTab, setActiveTab] = React.useState<'overview' | 'code' | 'web' | 'preview' | 'output'>('overview');
    const [expandedUrl, setExpandedUrl] = React.useState<string | null>(null);
    const [activeIframeUrl, setActiveIframeUrl] = React.useState<string | null>(null);

    const isExplorer = sidebarTab === 'explorer';
    const selectedNode = isExplorer
        ? flowData?.nodes.find((n: any) => n.id === selectedExplorerNodeId)
        : nodes.find(n => n.id === selectedNodeId);

    // Auto-switch tabs based on node type/content when selection changes
    React.useEffect(() => {
        if (!selectedNode) return;

        const nodeType = selectedNode.data.type;
        const nodeLabel = selectedNode.data.label?.toLowerCase() || '';

        // Reset web tab state when switching nodes
        setExpandedUrl(null);
        setActiveIframeUrl(null);

        // Switch to appropriate tab based on agent type
        if (nodeLabel.includes('retriever')) {
            setActiveTab('web');
        } else if (nodeType === 'Summarizer' || nodeType === 'Evaluator' ||
            nodeLabel.includes('formatter') || nodeLabel.includes('summarizer')) {
            setActiveTab('preview');
        } else if (nodeType === 'Coder') {
            setActiveTab('code');
        } else if (selectedNodeId) {
            setActiveTab('overview');
        }
    }, [selectedNodeId, selectedNode?.data.type, selectedNode?.data.label]);

    if (sidebarTab === 'rag') {
        return <DocumentAssistant />;
    }

    const effectiveSelectedNodeId = isExplorer ? selectedExplorerNodeId : selectedNodeId;

    if (!effectiveSelectedNodeId) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
                <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4">
                    <Terminal className="w-8 h-8 opacity-50" />
                </div>
                <h3 className="font-semibold text-foreground mb-2">Agent Inspector</h3>
                <p className="text-sm max-w-[200px]">Select a node in the graph to view its runtime details, code, and output.</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-card border-l border-border">
            {/* Sticky Header */}
            <div className="p-4 border-b border-border bg-card/95 backdrop-blur z-10">
                <div className="flex items-center gap-2 mb-2">
                    <div className={cn(
                        "w-2 h-2 rounded-full",
                        selectedNode?.data.status === 'completed' ? "bg-green-500" :
                            selectedNode?.data.status === 'running' ? "bg-yellow-500 animate-pulse" :
                                selectedNode?.data.status === 'waiting_input' ? "bg-yellow-400 animate-pulse" :
                                    selectedNode?.data.status === 'failed' ? "bg-red-500" : "bg-white/20"
                    )} />
                    <span className="font-mono font-bold text-sm tracking-wide uppercase text-foreground">
                        {selectedNode?.data.label || "Unknown Agent"}
                    </span>
                    <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                        {selectedNode?.id}
                    </span>
                </div>
                {/* Truncated Prompt Header */}
                <div className="text-xs text-muted-foreground line-clamp-2 font-medium border-l-2 border-primary/20 pl-2">
                    {selectedNode?.data.prompt || "No prompt available for this agent."}
                </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center border-b border-border px-2">
                <PanelTab label="Overview" active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} icon={<Terminal className="w-3 h-3" />} />
                <PanelTab label="Code" active={activeTab === 'code'} onClick={() => setActiveTab('code')} icon={<Code2 className="w-3 h-3" />} />
                <PanelTab label="Web" active={activeTab === 'web'} onClick={() => setActiveTab('web')} icon={<Globe className="w-3 h-3" />} />
                <PanelTab label="Preview" active={activeTab === 'preview'} onClick={() => setActiveTab('preview')} icon={<Eye className="w-3 h-3" />} />
                <PanelTab label="Stats" active={activeTab === 'output'} onClick={() => setActiveTab('output')} icon={<Terminal className="w-3 h-3" />} />
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {activeTab === 'overview' && (
                    <div className="p-4 space-y-6 overflow-y-auto h-full font-mono text-sm select-text">

                        {/* Section: User Query (Global) */}
                        {!isExplorer && currentRun && (
                            <div className="space-y-2">
                                <div className="text-xs uppercase tracking-widest text-white/50 font-bold flex items-center gap-2 select-none">
                                    <Terminal className="w-3 h-3" /> User Query
                                </div>
                                <div className="p-1 bg-white/5 rounded-md text-foreground/90 leading-relaxed text-lg border border-white/10 select-text font-sans">
                                    {currentRun.name}
                                </div>
                            </div>
                        )}

                        {/* Section: Agent Role (System Prompt) */}
                        <div className="space-y-2">
                            <div className="text-xs uppercase tracking-widest text-primary/70 font-bold flex items-center gap-2 select-none">
                                <Brain className="w-3 h-3" /> Agent Goal
                            </div>
                            <div className="p-3 bg-muted/50 rounded-md text-foreground/90 leading-relaxed text-xs border border-border/50 select-text">
                                {selectedNode?.data.prompt || "N/A"}
                            </div>
                        </div>

                        {/* Section: User Input (Clarification) */}
                        {selectedNode?.data.status === 'waiting_input' && (
                            <ClarificationInput selectedNode={selectedNode} codeContent={codeContent} />
                        )}

                        {/* Logic Steps (for Explorer) */}
                        {isExplorer && selectedNode?.data && (
                            <div className="space-y-6">
                                {/* Description */}
                                {selectedNode.data.description && (
                                    <div className="space-y-1">
                                        <div className="text-[10px] uppercase text-neon-yellow/60 font-bold tracking-widest">
                                            Component Mission
                                        </div>
                                        <div className="text-sm text-foreground leading-relaxed bg-muted/50 p-3 rounded-lg border border-border/50">
                                            {selectedNode.data.description}
                                        </div>
                                    </div>
                                )}

                                {/* Attributes */}
                                {selectedNode.data.attributes && selectedNode.data.attributes.length > 0 && (
                                    <div className="space-y-2">
                                        <div className="text-[10px] uppercase text-neon-yellow/60 font-bold tracking-widest">
                                            Technical Attributes
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {selectedNode.data.attributes.map((attr: string, idx: number) => (
                                                <span key={idx} className="px-2 py-0.5 bg-neon-yellow/10 border border-neon-yellow/20 text-neon-yellow text-[10px] rounded font-bold uppercase tracking-tighter">
                                                    {attr}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Details */}
                                {selectedNode.data.details && (
                                    <div className="space-y-2">
                                        <div className="text-[10px] uppercase text-neon-yellow font-bold tracking-widest pb-1 border-b border-neon-yellow/20 flex items-center justify-between">
                                            Implementation Details
                                            <span className="text-[9px] text-muted-foreground font-normal">Internal Logic</span>
                                        </div>
                                        <ul className="space-y-2 pl-1 select-text">
                                            {selectedNode.data.details.map((detail: string, idx: number) => (
                                                <li key={idx} className="flex gap-2 items-start group">
                                                    <div className="mt-1.5 h-1 w-1 rounded-full bg-neon-yellow opacity-40 group-hover:opacity-100 transition-opacity" />
                                                    <span className="text-[11px] leading-relaxed text-muted-foreground group-hover:text-foreground transition-colors">
                                                        {detail}
                                                    </span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Section: I/O Context */}
                        {!isExplorer && (
                            <div className="grid grid-cols-2 gap-2 select-none">
                                <div className="space-y-1">
                                    <div className="text-[10px] uppercase text-muted-foreground font-semibold">Inputs (Reads)</div>
                                    <div className="flex flex-wrap gap-1">
                                        {selectedNode?.data.reads?.length ? selectedNode?.data.reads.map((r: string) => (
                                            <span key={r} className="text-[10px] px-1.5 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded select-text">
                                                {r}
                                            </span>
                                        )) : <span className="text-[10px] text-muted-foreground italic">None</span>}
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <div className="text-[10px] uppercase text-muted-foreground font-semibold">Outputs (Writes)</div>
                                    <div className="flex flex-wrap gap-1">
                                        {selectedNode?.data.writes?.length ? selectedNode?.data.writes.map((w: string) => (
                                            <span key={w} className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-400 border border-green-500/20 rounded select-text">
                                                {w}
                                            </span>
                                        )) : <span className="text-[10px] text-muted-foreground italic">None</span>}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Section: Performance */}
                        {!isExplorer && (
                            <div className="p-3 bg-muted/50 rounded-lg flex items-center justify-between border border-border/50 select-none">
                                <div className="flex items-center gap-2">
                                    <Clock className="w-3 h-3 text-muted-foreground" />
                                    <span className="text-xs text-muted-foreground">Duration:</span>
                                    <span className="text-xs text-foreground font-mono">
                                        {typeof selectedNode?.data.execution_time === 'number'
                                            ? `${selectedNode.data.execution_time.toFixed(2)}s`
                                            : selectedNode?.data.execution_time || "0s"}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">Cost:</span>
                                    <span className="text-xs text-green-400 font-mono">
                                        ${selectedNode?.data.cost?.toFixed(6) || "0.000000"}
                                    </span>
                                </div>
                            </div>
                        )}

                        {/* Section: Logs/Output Snippet */}
                        <div className="space-y-2">
                            <div className="text-xs uppercase tracking-widest text-primary/70 font-bold border-b border-border pb-1 select-none">
                                Execution Output
                            </div>
                            {logs.map((log, i) => (
                                <div key={i} className="flex flex-col gap-1 pl-2 border-l border-border select-text">
                                    <div className="text-[10px] text-muted-foreground uppercase opacity-70 select-none">
                                        {log.split(':')[0]}
                                    </div>
                                    <div className="text-foreground/80 whitespace-pre-wrap break-words text-xs">
                                        {log.split(':').slice(1).join(':').trim()}
                                    </div>
                                </div>
                            ))}
                            {/* Display Raw Result Keys if available */}
                            {(() => {
                                try {
                                    const parsed = JSON.parse(codeContent);
                                    return (
                                        <div className="mt-2 space-y-1 select-text">
                                            {Object.entries(parsed).slice(0, 5).map(([k, v]) => {
                                                if (typeof v === 'object' || String(v).length > 200 || k === 'code_variants') return null;
                                                return (
                                                    <div key={k} className="flex justify-between text-xs py-0.5 border-b border-border/50">
                                                        <span className="text-muted-foreground select-none">{k}</span>
                                                        <span className="text-foreground truncate max-w-[150px]">{String(v)}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )
                                } catch { return null; }
                            })()}
                        </div>
                    </div>
                )}
                {activeTab === 'code' && (
                    <Editor
                        height="100%"
                        defaultLanguage="python"
                        theme="vs-dark"
                        value={(() => {
                            try {
                                // Smart Code Extraction:
                                // The node output may be a Python dict string (single quotes) not JSON
                                // We need to extract the actual Python code from code_variants
                                const raw = codeContent; // This is node.data.output (stringified)
                                if (!raw) return "# No output";

                                // Try to parse as JSON first
                                let parsed;
                                try {
                                    parsed = JSON.parse(raw);
                                } catch {
                                    // If JSON parse fails, try to convert Python dict format to JSON
                                    // Python uses single quotes, True/False/None vs true/false/null
                                    const jsonified = raw
                                        .replace(/'/g, '"')
                                        .replace(/\bTrue\b/g, 'true')
                                        .replace(/\bFalse\b/g, 'false')
                                        .replace(/\bNone\b/g, 'null');
                                    try {
                                        parsed = JSON.parse(jsonified);
                                    } catch {
                                        // If still fails, try regex extraction for code_variants
                                        const codeMatch = raw.match(/['"]CODE_\w+['"]\s*:\s*['"]([^]*?)['"]\s*[,}]/);
                                        if (codeMatch) {
                                            // Unescape the code string
                                            return codeMatch[1]
                                                .replace(/\\n/g, '\n')
                                                .replace(/\\t/g, '\t')
                                                .replace(/\\'/g, "'")
                                                .replace(/\\"/g, '"');
                                        }
                                        return raw; // Return raw if all parsing fails
                                    }
                                }

                                // 1. Check for Code Variants (Common in Agents)
                                if (parsed.code_variants && typeof parsed.code_variants === 'object') {
                                    const firstKey = Object.keys(parsed.code_variants)[0];
                                    const code = parsed.code_variants[firstKey];
                                    if (typeof code === 'string' && code.trim()) {
                                        return code;
                                    }
                                }

                                // 2. Check for Execution Result
                                if (parsed.execution_result) {
                                    return JSON.stringify(parsed.execution_result, null, 2);
                                }

                                // 3. Return formatted JSON if no code found
                                return JSON.stringify(parsed, null, 2);
                            } catch {
                                return codeContent || '# No code available';
                            }
                        })()}
                        options={{
                            minimap: { enabled: false },
                            fontSize: 13,
                            fontFamily: 'JetBrains Mono, Menlo, monospace',
                            scrollBeyondLastLine: false,
                            padding: { top: 16 },
                            wordWrap: 'on'
                        }}
                    />
                )}

                {
                    activeTab === 'output' && (
                        <div className="p-4 font-mono text-xs space-y-4 overflow-y-auto h-full select-text">
                            <div className="text-green-400 font-bold border-b border-border pb-2 mb-2 select-none">
                                # Node Execution Details
                            </div>
                            {logs.map((log, i) => (
                                <div key={i} className="flex flex-col gap-1 border-l-2 border-primary/30 pl-3 py-1 bg-muted/50 rounded-r hover:bg-muted transition-colors">
                                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest opacity-70 select-none">
                                        {log.split(':')[0]}
                                    </div>
                                    <div className="text-foreground whitespace-pre-wrap break-words">
                                        {log.split(':').slice(1).join(':').trim()}
                                    </div>
                                </div>
                            ))}
                            {/* Display Raw Result Keys if available */}
                            {(() => {
                                try {
                                    const parsed = JSON.parse(codeContent);
                                    return (
                                        <div className="mt-4 pt-4 border-t border-border">
                                            <div className="text-yellow-400 font-bold mb-2 select-none"># Results</div>
                                            {Object.entries(parsed).map(([k, v]) => {
                                                if (typeof v === 'object' || String(v).length > 200) return null; // Skip non-primitive or huge
                                                return (
                                                    <div key={k} className="flex justify-between border-b border-border/50 py-1">
                                                        <span className="text-muted-foreground select-none">{k}</span>
                                                        <span className="text-foreground">{String(v)}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )
                                } catch { return null; }
                            })()}
                        </div>
                    )
                }

                {
                    activeTab === 'web' && (
                        <div className="h-full flex flex-col overflow-hidden select-text">
                            {(() => {
                                // Extract URLs from RetrieverAgent output
                                interface UrlInfo {
                                    url: string;
                                    content: string;
                                    domain: string;
                                }

                                let urls: UrlInfo[] = [];
                                let parsed: any = null;

                                try {
                                    parsed = JSON.parse(codeContent);

                                    // Recursive function to find URLs in any object/array
                                    const findUrlsRecursive = (obj: any) => {
                                        if (!obj || typeof obj !== 'object') return;

                                        // If it's an array, check each item
                                        if (Array.isArray(obj)) {
                                            for (const item of obj) {
                                                if (typeof item === 'string' && item.startsWith('http')) {
                                                    addUrl(item);
                                                } else if (item && typeof item === 'object') {
                                                    // Check if it's a {url, content} pair
                                                    if ('url' in item && typeof item.url === 'string' && item.url.startsWith('http')) {
                                                        addUrl(item.url, item.content);
                                                    }
                                                    findUrlsRecursive(item);
                                                }
                                            }
                                        } else {
                                            // If it's an object, check each property
                                            for (const [key, value] of Object.entries(obj)) {
                                                // Handle arrays of URLs in any property (e.g. found_urls: ["http..."])
                                                if (Array.isArray(value)) {
                                                    value.forEach(item => {
                                                        if (typeof item === 'string' && item.startsWith('http')) {
                                                            addUrl(item);
                                                        } else if (item && typeof item === 'object' && (item as any).url && typeof (item as any).url === 'string' && (item as any).url.startsWith('http')) {
                                                            addUrl((item as any).url, (item as any).content);
                                                        }
                                                    });
                                                }

                                                if (typeof value === 'string' && value.startsWith('http')) {
                                                    addUrl(value);
                                                } else {
                                                    findUrlsRecursive(value);
                                                }
                                            }
                                        }
                                    };

                                    const addUrl = (url: string, content?: any) => {
                                        try {
                                            const domain = new URL(url).hostname;
                                            if (!urls.find(u => u.url === url)) {
                                                urls.push({
                                                    url,
                                                    content: typeof content === 'string' ? content : (content ? JSON.stringify(content) : 'No content extracted'),
                                                    domain
                                                });
                                            }
                                        } catch { }
                                    };

                                    findUrlsRecursive(parsed);

                                    // 2. Scan iterations/ReAct logs (where MCP tool results live)
                                    if (selectedNode?.data?.iterations && Array.isArray(selectedNode.data.iterations)) {
                                        selectedNode.data.iterations.forEach((iter: any) => {
                                            if (iter.output) {
                                                findUrlsRecursive(iter.output);

                                                // Check for tool_result
                                                if (iter.output.iteration_context && iter.output.iteration_context.tool_result) {
                                                    const toolResult = iter.output.iteration_context.tool_result;
                                                    if (typeof toolResult === 'string') {
                                                        const urlRegex = /https?:\/\/[^\s'"]+/g;
                                                        const matches = toolResult.match(urlRegex);
                                                        if (matches) {
                                                            matches.forEach(url => addUrl(url, toolResult));
                                                        }
                                                    }
                                                }
                                            }

                                            // Check for Saved Execution Results (Code Execution)
                                            if (iter.execution_result) {
                                                findUrlsRecursive(iter.execution_result);

                                                // Handle stringified Python lists in result block
                                                // e.g. "found_urls": "['http://...']"
                                                const resStr = JSON.stringify(iter.execution_result);
                                                const urlRegex = /https?:\/\/[^\s'"]+/g;
                                                const matches = resStr.match(urlRegex);
                                                if (matches) {
                                                    matches.forEach(url => {
                                                        // Clean up trailing chars often caught in stringified python lists like combined quote+bracket
                                                        const cleanUrl = url.replace(/['"\]]+$/, '');
                                                        addUrl(cleanUrl, "Execution Result");
                                                    });
                                                }
                                            }

                                            // Check for Saved Tool Results (MCP)
                                            if (iter.tool_result && typeof iter.tool_result === 'string') {
                                                const urlRegex = /https?:\/\/[^\s'"]+/g;
                                                const matches = (iter.tool_result as string).match(urlRegex);
                                                if (matches) matches.forEach((url: string) => addUrl(url, "Tool Result"));
                                            }
                                        });
                                    }

                                    // 3. Scan execution logs (stdout/stderr captured from Sandbox)
                                    if (selectedNode?.data?.execution_logs) {
                                        let logs = selectedNode.data.execution_logs;
                                        // Try to unescape if it looks like a JSON string or has escaped chars
                                        try {
                                            if (logs.startsWith('"') && logs.endsWith('"')) {
                                                logs = JSON.parse(logs);
                                            } else {
                                                logs = logs.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\'/g, "'");
                                            }
                                        } catch { }

                                        console.log("Web Tab Scanned Logs:", logs.slice(0, 200) + "...");

                                        // Look for "Link: https://..." or "Navigating to https://..."
                                        // We want to capture the URL specifically
                                        const navigationRegex = /(?:Navigating to|Visiting|Link:) (https?:\/\/[^\s'"]+)/gi;
                                        let navMatch;
                                        while ((navMatch = navigationRegex.exec(logs)) !== null) {
                                            if (navMatch[1]) addUrl(navMatch[1], "Navigation Log");
                                        }

                                        // Also generic URL scan
                                        const urlRegex = /https?:\/\/[^\s'"]+/g;
                                        const matches = logs.match(urlRegex);
                                        if (matches) {
                                            matches.forEach((url: string) => addUrl(url, "Log output"));
                                        }
                                    }

                                    // 4. Final fallback: Scan all text content in all iterations/code_variants
                                    const allContentStr = JSON.stringify({
                                        parsed,
                                        iterations: selectedNode?.data?.iterations
                                    });
                                    const globalUrlMatches = allContentStr.match(/https?:\/\/[^\s'"]+/g);
                                    if (globalUrlMatches) {
                                        globalUrlMatches.forEach(url => addUrl(url));
                                    }
                                } catch { }

                                // The state hooks are at the component level now

                                if (urls.length === 0) {
                                    console.log("Web Tab Debug: No URLs found in", parsed);
                                    return (
                                        <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-4 p-8 overflow-auto">
                                            <Globe className="w-16 h-16 opacity-20" />
                                            <div className="text-center mb-4">
                                                <p className="text-sm font-medium mb-1">List of URLs Found will be populated here</p>
                                                <p className="text-xs opacity-70">Waiting to visit web pages</p>
                                            </div>

                                            {/* DEBUG: Dump node data to see what we actually have */}
                                            <div className="w-full text-left bg-muted p-4 rounded text-[10px] text-foreground font-mono whitespace-pre overflow-auto max-h-96 border border-border">
                                                <div className="font-bold text-red-500 mb-2">RAW DATA DUMP</div>
                                                {JSON.stringify({
                                                    iterations: selectedNode?.data?.iterations,
                                                    execution_result: selectedNode?.data?.execution_result,
                                                    tool_result_scan: parsed
                                                }, null, 2)}
                                            </div>
                                        </div>
                                    );
                                }

                                console.log("Web Tab Debug: Found URLs", urls);

                                return (
                                    <>
                                        {/* URL List */}
                                        <div className="flex-1 overflow-y-auto p-3 space-y-2">
                                            <div className="text-xs uppercase text-muted-foreground font-bold mb-3 flex items-center gap-2">
                                                <Globe className="w-3 h-3" />
                                                Web Sources ({urls.length})
                                            </div>

                                            {urls.map((urlInfo, idx) => (
                                                <div key={idx} className="border border-border rounded-lg overflow-hidden bg-muted">
                                                    {/* Accordion Header */}
                                                    <button
                                                        onClick={() => setExpandedUrl(expandedUrl === urlInfo.url ? null : urlInfo.url)}
                                                        className="w-full p-3 flex items-center gap-3 hover:bg-muted/50 transition-colors text-left"
                                                    >
                                                        <div className={cn(
                                                            "w-5 h-5 flex items-center justify-center transition-transform",
                                                            expandedUrl === urlInfo.url && "rotate-90"
                                                        )}>
                                                            <svg className="w-3 h-3 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                            </svg>
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <div className="text-xs font-medium text-primary truncate">{urlInfo.domain}</div>
                                                            <div className="text-[10px] text-muted-foreground truncate">{urlInfo.url}</div>
                                                        </div>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setActiveIframeUrl(urlInfo.url);
                                                                setExpandedUrl(urlInfo.url);
                                                            }}
                                                            className="px-2 py-1 text-[10px] bg-primary/10 text-primary rounded hover:bg-primary/20 transition-colors"
                                                        >
                                                            Open
                                                        </button>
                                                    </button>

                                                    {/* Accordion Content */}
                                                    {expandedUrl === urlInfo.url && (
                                                        <div className="px-4 pb-4 pt-2 border-t border-border/50">

                                                            {/* Iframe View */}
                                                            {activeIframeUrl === urlInfo.url ? (
                                                                <div className="flex flex-col gap-2">
                                                                    <div className="flex items-center justify-between mb-1">
                                                                        <span className="text-xs text-muted-foreground font-medium">Web Preview (50% Zoom)</span>
                                                                        <button
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                setActiveIframeUrl(null);
                                                                            }}
                                                                            className="text-[10px] text-blue-400 hover:text-blue-300"
                                                                        >
                                                                            Switch to Text Limit
                                                                        </button>
                                                                    </div>
                                                                    <div className="w-full h-96 bg-white overflow-hidden rounded relative border border-border">
                                                                        <div className="absolute inset-0 w-[200%] h-[200%] origin-top-left scale-50">
                                                                            <iframe
                                                                                src={urlInfo.url}
                                                                                className="w-full h-full border-none"
                                                                                title="Web Preview"
                                                                                sandbox="allow-scripts allow-same-origin"
                                                                            />
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            ) : (
                                                                /* Text Content Preview */
                                                                <>
                                                                    <div className="text-xs text-muted-foreground mb-2 font-medium">Content Preview:</div>
                                                                    <div className="text-xs text-foreground/80 bg-black/20 p-3 rounded max-h-40 overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
                                                                        {urlInfo.content.slice(0, 500)}
                                                                        {urlInfo.content.length > 500 && '...'}
                                                                    </div>
                                                                    <a
                                                                        href={urlInfo.url}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="mt-2 inline-flex items-center gap-1 text-[10px] text-blue-400 hover:underline"
                                                                    >
                                                                        Open in new tab →
                                                                    </a>
                                                                </>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>

                                    </>
                                );
                            })()}
                        </div>
                    )
                }

                {
                    activeTab === 'preview' && (
                        <div className="h-full p-6 overflow-auto bg-card">
                            {(() => {
                                let formatContent: string | null = null;
                                let contentType: 'html' | 'markdown' = 'markdown';

                                // Helper to clean escaped content
                                const cleanContent = (value: string) => {
                                    return value
                                        .replace(/\\n/g, '\n')
                                        .replace(/\\t/g, '\t')
                                        .replace(/\\'/g, "'")
                                        .replace(/\\"/g, '"');
                                };

                                // Helper to check if content is HTML
                                const isHtml = (value: string) => {
                                    return value.includes('<div') || value.includes('<h1') ||
                                        value.includes('<p>') || value.includes('<html') ||
                                        value.includes('<table') || value.includes('<ul');
                                };

                                try {
                                    // PRIORITY: Use live node data directly to ensure auto-refresh
                                    let parsed: any = selectedNode?.data?.output;

                                    // If no direct output, try codeContent (fallback)
                                    if (!parsed && codeContent) {
                                        try {
                                            parsed = JSON.parse(codeContent);
                                        } catch {
                                            // Handle python-style dict strings
                                            const jsonified = codeContent
                                                .replace(/'/g, '"')
                                                .replace(/\bTrue\b/g, 'true')
                                                .replace(/\bFalse\b/g, 'false')
                                                .replace(/\bNone\b/g, 'null');
                                            parsed = JSON.parse(jsonified);
                                        }
                                    }

                                    // Ensure parsed is an object
                                    if (typeof parsed !== 'object' || parsed === null) {
                                        // If output is a raw string (sometimes happens), treat it as content
                                        if (typeof parsed === 'string' && parsed.trim().length > 0) {
                                            // CRITICAL FIX: Try to parse as JSON *before* checking for HTML
                                            // A JSON string might contain HTML tags in its values, but we want the object, not the raw string.
                                            let isJsonString = false;
                                            if (parsed.trim().startsWith('{') || parsed.trim().startsWith('[')) {
                                                try {
                                                    const p = JSON.parse(parsed);
                                                    parsed = p; // It was a stringified JSON, continue to object logic
                                                    isJsonString = true;
                                                } catch {
                                                    // Parse failed, treat as string
                                                }
                                            }

                                            // Only if it wasn't a valid JSON string do we check for direct HTML content
                                            if (!isJsonString) {
                                                if (isHtml(parsed)) {
                                                    formatContent = parsed;
                                                    contentType = 'html';
                                                } else {
                                                    formatContent = parsed;
                                                }
                                            }
                                        }
                                    }

                                    // Generate Content from Object (if we have one)
                                    if (!formatContent && parsed && typeof parsed === 'object') {
                                        // PASS 1: Look for any key containing HTML content (prioritize actual formatted reports)
                                        for (const [key, value] of Object.entries(parsed)) {
                                            if (typeof value === 'string' && value.length > 100 && isHtml(value)) {
                                                formatContent = cleanContent(value);
                                                contentType = 'html';
                                                break;
                                            }
                                        }

                                        // PASS 2: If no HTML found, look for keys starting with 'formatted_'
                                        if (!formatContent) {
                                            const formattedKeys = Object.keys(parsed).filter(k => k.startsWith('formatted_'));
                                            for (const key of formattedKeys) {
                                                const value = parsed[key as keyof typeof parsed];
                                                if (typeof value === 'string' && value.length > 50) {
                                                    const cleaned = cleanContent(value);
                                                    formatContent = cleaned;
                                                    contentType = isHtml(cleaned) ? 'html' : 'markdown';
                                                    break;
                                                }
                                            }
                                        }

                                        // PASS 3: Fallback to markdown/content keys
                                        if (!formatContent) {
                                            const fallbackKeys = ['fallback_markdown', 'markdown', 'report', 'content', 'result'];
                                            for (const key of fallbackKeys) {
                                                const value = parsed[key as keyof typeof parsed];
                                                if (typeof value === 'string' && value.trim()) {
                                                    formatContent = cleanContent(value);
                                                    contentType = isHtml(formatContent) ? 'html' : 'markdown';
                                                    break;
                                                }
                                            }
                                        }
                                    }

                                    // Debug log to help verify updates
                                    // console.log("Preview Render:", { id: selectedNode?.id, hasOutput: !!selectedNode?.data?.output, formatContent: !!formatContent });

                                } catch (e) {
                                    console.error("Preview parsing error:", e);
                                    // If all parsing fails, try raw content from codeContent as last resort
                                    if (codeContent && !codeContent.startsWith('{')) {
                                        formatContent = codeContent.replace(/\\n/g, '\n');
                                    }
                                }

                                if (formatContent) {
                                    // Sanitize HTML for security
                                    const sanitizedHtml = contentType === 'html'
                                        ? DOMPurify.sanitize(formatContent)
                                        : formatContent;

                                    return (
                                        <div className="preview-content bg-muted p-6 rounded-lg border border-border select-text">
                                            <style>{`
                                                .preview-content h1 { font-size: 1.75rem; font-weight: bold; color: hsl(var(--primary)); margin-bottom: 1rem; }
                                                .preview-content h2 { font-size: 1.5rem; font-weight: bold; color: hsl(var(--primary)); margin-top: 1.5rem; margin-bottom: 0.75rem; border-bottom: 1px solid hsl(var(--border)); padding-bottom: 0.5rem; }
                                                .preview-content h3 { font-size: 1.25rem; font-weight: bold; color: hsl(var(--foreground)); margin-top: 1rem; margin-bottom: 0.5rem; }
                                                .preview-content h4 { font-size: 1.1rem; font-weight: 600; color: hsl(var(--muted-foreground)); margin-top: 0.75rem; margin-bottom: 0.5rem; }
                                                .preview-content p { color: hsl(var(--muted-foreground)); line-height: 1.6; margin-bottom: 0.75rem; }
                                                .preview-content ul, .preview-content ol { color: hsl(var(--muted-foreground)); padding-left: 1.5rem; margin-bottom: 1rem; }
                                                .preview-content li { margin-bottom: 0.25rem; }
                                                .preview-content table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
                                                .preview-content th { background: hsl(var(--muted)); color: hsl(var(--primary)); padding: 0.75rem; text-align: left; border: 1px solid hsl(var(--border)); font-weight: 600; }
                                                .preview-content td { padding: 0.75rem; border: 1px solid hsl(var(--border)); color: hsl(var(--muted-foreground)); }
                                                .preview-content tr:nth-child(even) td { background: hsl(var(--background)); }
                                                .preview-content strong, .preview-content b { color: hsl(var(--primary)); font-weight: 600; }
                                                .preview-content i, .preview-content em { color: hsl(var(--muted-foreground)); font-style: italic; }
                                                .preview-content a { color: #60a5fa; text-decoration: underline; }
                                                .preview-content code { background: hsl(var(--background)); padding: 0.2rem 0.4rem; border-radius: 4px; color: hsl(var(--primary)); border: 1px solid hsl(var(--border)); }
                                                .preview-content pre { background: hsl(var(--background)); padding: 1rem; border-radius: 8px; overflow-x: auto; border: 1px solid hsl(var(--border)); }
                                                .preview-content blockquote { border-left: 3px solid hsl(var(--primary)); padding-left: 1rem; color: hsl(var(--muted-foreground)); font-style: italic; }
                                                .preview-content .report { color: hsl(var(--foreground)); }
                                            `}</style>
                                            {contentType === 'html' ? (
                                                <div dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />
                                            ) : (
                                                <ReactMarkdown>{formatContent}</ReactMarkdown>
                                            )}
                                        </div>
                                    );
                                }

                                return (
                                    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                                        <FileCode className="w-12 h-12 mb-4 opacity-30" />
                                        <p className="text-sm">No formatted output available for this node.</p>
                                        <p className="text-xs mt-2 opacity-70">Select a FormatterAgent or SummarizerAgent to see rendered output.</p>
                                    </div>
                                );
                            })()}
                        </div>
                    )
                }
            </div >
        </div >
    );
};
