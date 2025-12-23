import React from 'react';
import { Code2, Terminal, Globe, FileCode, CheckCircle2, Eye, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import Editor from "@monaco-editor/react";
import ReactMarkdown from 'react-markdown';

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

export const WorkspacePanel: React.FC = () => {
    const { codeContent, webUrl, logs, selectedNodeId, nodes } = useAppStore();
    const [activeTab, setActiveTab] = React.useState<'overview' | 'code' | 'web' | 'preview' | 'output'>('overview');

    const selectedNode = nodes.find(n => n.id === selectedNodeId);

    // Auto-switch tabs based on node type/content when selection changes
    React.useEffect(() => {
        if (!selectedNode) return;

        const nodeType = selectedNode.data.type;
        const nodeLabel = selectedNode.data.label?.toLowerCase() || '';

        // Switch to Preview for agents that produce formatted output
        if (nodeType === 'Summarizer' || nodeType === 'Evaluator' ||
            nodeLabel.includes('formatter') || nodeLabel.includes('summarizer')) {
            setActiveTab('preview');
        } else if (nodeType === 'Coder') {
            setActiveTab('code');
        } else if (selectedNodeId) {
            setActiveTab('overview');
        }
    }, [selectedNodeId, selectedNode?.data.type, selectedNode?.data.label]);

    if (!selectedNodeId) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
                <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
                    <Terminal className="w-8 h-8 opacity-50" />
                </div>
                <h3 className="font-semibold text-foreground mb-2">Agent Inspector</h3>
                <p className="text-sm max-w-[200px]">Select a node in the graph to view its runtime details, code, and output.</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-charcoal-900 border-l border-border">
            {/* Sticky Header */}
            <div className="p-4 border-b border-border bg-charcoal-900/95 backdrop-blur z-10">
                <div className="flex items-center gap-2 mb-2">
                    <div className={cn(
                        "w-2 h-2 rounded-full",
                        selectedNode?.data.status === 'completed' ? "bg-green-500" :
                            selectedNode?.data.status === 'running' ? "bg-yellow-500 animate-pulse" :
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
                <PanelTab label="Output" active={activeTab === 'output'} onClick={() => setActiveTab('output')} icon={<Terminal className="w-3 h-3" />} />
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {activeTab === 'overview' && (
                    <div className="p-4 space-y-6 overflow-y-auto h-full font-mono text-sm">

                        {/* Section: Prompt */}
                        <div className="space-y-2">
                            <div className="text-xs uppercase tracking-widest text-primary/70 font-bold flex items-center gap-2">
                                <Terminal className="w-3 h-3" /> Original Prompt
                            </div>
                            <div className="p-3 bg-white/5 rounded-md text-foreground/90 leading-relaxed text-xs border border-white/5">
                                {selectedNode?.data.prompt || "N/A"}
                            </div>
                        </div>

                        {/* Section: I/O Context */}
                        <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase text-muted-foreground font-semibold">Inputs (Reads)</div>
                                <div className="flex flex-wrap gap-1">
                                    {selectedNode?.data.reads?.length ? selectedNode?.data.reads.map(r => (
                                        <span key={r} className="text-[10px] px-1.5 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                                            {r}
                                        </span>
                                    )) : <span className="text-[10px] text-muted-foreground italic">None</span>}
                                </div>
                            </div>
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase text-muted-foreground font-semibold">Outputs (Writes)</div>
                                <div className="flex flex-wrap gap-1">
                                    {selectedNode?.data.writes?.length ? selectedNode?.data.writes.map(w => (
                                        <span key={w} className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-400 border border-green-500/20 rounded">
                                            {w}
                                        </span>
                                    )) : <span className="text-[10px] text-muted-foreground italic">None</span>}
                                </div>
                            </div>
                        </div>

                        {/* Section: Performance */}
                        <div className="p-3 bg-black/20 rounded-lg flex items-center justify-between border border-white/5">
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

                        {/* Section: Logs/Output Snippet */}
                        <div className="space-y-2">
                            <div className="text-xs uppercase tracking-widest text-primary/70 font-bold border-b border-white/10 pb-1">
                                Execution Output
                            </div>
                            {logs.map((log, i) => (
                                <div key={i} className="flex flex-col gap-1 pl-2 border-l border-white/10">
                                    <div className="text-[10px] text-muted-foreground uppercase opacity-70">
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
                                        <div className="mt-2 space-y-1">
                                            {Object.entries(parsed).slice(0, 5).map(([k, v]) => {
                                                if (typeof v === 'object' || String(v).length > 200 || k === 'code_variants') return null;
                                                return (
                                                    <div key={k} className="flex justify-between text-xs py-0.5 border-b border-white/5">
                                                        <span className="text-muted-foreground">{k}</span>
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
                        <div className="p-4 font-mono text-xs space-y-4 overflow-y-auto h-full">
                            <div className="text-green-400 font-bold border-b border-white/10 pb-2 mb-2">
                                # Node Execution Details
                            </div>
                            {logs.map((log, i) => (
                                <div key={i} className="flex flex-col gap-1 border-l-2 border-primary/30 pl-3 py-1 bg-white/5 rounded-r hover:bg-white/10 transition-colors">
                                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest opacity-70">
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
                                        <div className="mt-4 pt-4 border-t border-white/10">
                                            <div className="text-yellow-400 font-bold mb-2"># Results</div>
                                            {Object.entries(parsed).map(([k, v]) => {
                                                if (typeof v === 'object' || String(v).length > 200) return null; // Skip non-primitive or huge
                                                return (
                                                    <div key={k} className="flex justify-between border-b border-white/5 py-1">
                                                        <span className="text-muted-foreground">{k}</span>
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
                        <div className="h-full flex flex-col">
                            <div className="p-2 border-b border-border bg-background flex gap-2">
                                <div className="flex-1 bg-accent/50 rounded-md px-3 py-1.5 text-xs text-muted-foreground truncate font-mono">
                                    {webUrl || "https://example.com"}
                                </div>
                            </div>
                            {webUrl ? (
                                <iframe src={webUrl} className="w-full h-full bg-white" title="Web Preview" />
                            ) : (
                                <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-4">
                                    <Globe className="w-12 h-12 opacity-20" />
                                    <span className="text-sm">No agent browser session active</span>
                                </div>
                            )}
                        </div>
                    )
                }

                {
                    activeTab === 'preview' && (
                        <div className="h-full p-6 overflow-auto bg-charcoal-900">
                            {(() => {
                                let formatContent: string | null = null;
                                let contentType: 'html' | 'markdown' = 'markdown';

                                try {
                                    // First try to parse as JSON
                                    let parsed: Record<string, unknown>;
                                    try {
                                        parsed = JSON.parse(codeContent);
                                    } catch {
                                        // Try converting Python dict format
                                        const jsonified = codeContent
                                            .replace(/'/g, '"')
                                            .replace(/\bTrue\b/g, 'true')
                                            .replace(/\bFalse\b/g, 'false')
                                            .replace(/\bNone\b/g, 'null');
                                        parsed = JSON.parse(jsonified);
                                    }

                                    // Look for formatted content in various keys
                                    const candidates = [
                                        // Keys that typically have formatted output
                                        ...Object.keys(parsed).filter(k => k.startsWith('formatted_')),
                                        'formatted_report', 'report', 'html_output', 'output',
                                        'fallback_markdown', 'markdown', 'content', 'result'
                                    ];

                                    for (const key of candidates) {
                                        const value = parsed[key];
                                        if (typeof value === 'string' && value.trim()) {
                                            // Clean up escaped newlines and other escapes
                                            let cleaned = value
                                                .replace(/\\n/g, '\n')
                                                .replace(/\\t/g, '\t')
                                                .replace(/\\'/g, "'")
                                                .replace(/\\"/g, '"');

                                            // Detect if it's HTML
                                            if (cleaned.includes('<div') || cleaned.includes('<h1') ||
                                                cleaned.includes('<p>') || cleaned.includes('<html')) {
                                                contentType = 'html';
                                            }

                                            formatContent = cleaned;
                                            break;
                                        }
                                    }
                                } catch {
                                    // If all parsing fails, try to use raw content
                                    if (codeContent && !codeContent.startsWith('{')) {
                                        formatContent = codeContent.replace(/\\n/g, '\n');
                                    }
                                }

                                if (formatContent) {
                                    return (
                                        <div className="prose prose-invert prose-sm max-w-none 
                                            prose-headings:text-primary prose-headings:font-bold 
                                            prose-p:text-foreground/90 prose-p:leading-relaxed
                                            prose-strong:text-primary prose-li:text-foreground/80
                                            prose-a:text-blue-400 prose-code:text-green-400
                                            prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg
                                            bg-charcoal-800 p-6 rounded-lg border border-white/10">
                                            {contentType === 'html' ? (
                                                <div dangerouslySetInnerHTML={{ __html: formatContent }} />
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
