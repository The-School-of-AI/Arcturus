import React, { useState, useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Play, XCircle, Terminal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

interface MonacoWidgetProps {
    title?: string;
    code: string;
    language?: string;
    theme?: string;
    onCodeChange?: (newCode: string) => void;
    onClick?: () => void;
}

const MonacoWidget: React.FC<MonacoWidgetProps> = ({
    title = 'Code Editor',
    code,
    language = 'javascript',
    theme = 'vs-dark',
    onCodeChange
}) => {
    const [logs, setLogs] = useState<{ type: 'info' | 'error' | 'success', msg: string, time: string }[]>([]);
    const logEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const addLog = (msg: string, type: 'info' | 'error' | 'success' = 'info') => {
        setLogs(prev => [...prev.slice(-49), {
            type,
            msg: typeof msg === 'object' ? JSON.stringify(msg, null, 2) : String(msg),
            time: new Date().toLocaleTimeString()
        }]);
    };

    const handleRun = async () => {
        addLog('🚀 Starting execution...', 'info');
        try {
            const bridge = {
                Arcturus: {
                    ki: {
                        sync: async () => {
                            addLog('🔄 Triggering Memory Synchronization...', 'info');
                            try {
                                await axios.post(`${API_BASE}/remme/scan`);
                                addLog('✅ Memory synchronization triggered in background.', 'success');
                            } catch (e) {
                                addLog(`❌ Memory sync failed: ${e}`, 'error');
                            }
                        },
                        search: async (q: string) => {
                            addLog(`🔎 Searching Memory for: "${q}"...`, 'info');
                            try {
                                const resp = await axios.get(`${API_BASE}/remme/memories`);
                                // Reverted to naive match for P06 project boundary
                                const matches = (resp.data.memories || []).filter((m: any) =>
                                    m.text.toLowerCase().includes(q.toLowerCase())
                                );
                                addLog(`✅ Found ${matches.length} memory matches (naive match)`, 'success');
                                return matches;
                            } catch (e) {
                                addLog(`❌ Memory search failed: ${e}`, 'error');
                                return [];
                            }
                        }
                    },
                    rag: {
                        search: async (q: string) => {
                            addLog(`📚 Querying RAG: "${q}"...`, 'info');
                            try {
                                const resp = await axios.get(`${API_BASE}/rag/search?query=${q}`);
                                addLog(`✅ RAG returned ${resp.data.results?.length || 0} snippets`, 'success');
                                return resp.data.results;
                            } catch (e) {
                                addLog(`❌ RAG search failed: ${e}`, 'error');
                                return [];
                            }
                        }
                    },
                    agents: {
                        spawn: async (type: string, props: any) => {
                            addLog(`🤖 Spawning Agent [${type}] with: ${JSON.stringify(props)}`, 'info');
                            return {
                                run: async () => {
                                    addLog(`⚙️ Agent [${type}] completed task.`, 'success');
                                    return { status: 'success', data: 'Operation complete' };
                                }
                            };
                        }
                    }
                },
                Surface: {
                    updateMetadata: (meta: any) => {
                        addLog(`🔧 Project Metadata updated: ${JSON.stringify(meta)}`, 'info');
                    }
                },
                print: (msg: any) => addLog(msg, 'info'),
                log: (msg: any) => addLog(msg, 'info'),
                error: (msg: any) => addLog(msg, 'error')
            };

            // Execute in an async context
            const AsyncFunction = Object.getPrototypeOf(async function () { }).constructor;
            const script = new AsyncFunction('Arcturus', 'Surface', 'console', 'print', code);

            // Redirect console.log within the script
            const customConsole = {
                log: (...args: any[]) => addLog(args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' '), 'info'),
                error: (...args: any[]) => addLog(args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' '), 'error'),
                info: (...args: any[]) => addLog(args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' '), 'info')
            };

            await script(bridge.Arcturus, bridge.Surface, customConsole, bridge.print);
            addLog('✨ Execution finished successfully.', 'success');
        } catch (err) {
            addLog(`${err}`, 'error');
        }
    };

    return (
        <div className="w-full flex flex-col border border-border/40 rounded-xl overflow-hidden shadow-2xl bg-background/50 backdrop-blur-sm">
            {/* Header / Toolbar */}
            <div className="flex items-center justify-between px-3 py-2 bg-muted/30 border-b border-border/20">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                    <span className="text-[10px] font-bold uppercase tracking-widest opacity-70">{title}</span>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setLogs([])}
                        className="h-7 px-2 text-[10px] font-bold uppercase tracking-tight gap-1.5 opacity-40 hover:opacity-100"
                    >
                        <XCircle className="w-3 h-3" />
                        Clear Console
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleRun}
                        className="h-7 px-2 text-[10px] font-bold uppercase tracking-tight gap-1.5 bg-primary/10 text-cyan-400 hover:bg-cyan-500/20 transition-colors"
                    >
                        <Play className="w-3 h-3 fill-current" />
                        Run Script
                    </Button>
                </div>
            </div>

            <div className="flex flex-col md:flex-row h-[500px]">
                <div className="flex-1 min-w-0 border-r border-border/10">
                    <Editor
                        height="100%"
                        defaultLanguage={language}
                        defaultValue={code}
                        theme={theme}
                        options={{
                            minimap: { enabled: false },
                            fontSize: 12,
                            scrollBeyondLastLine: false,
                            automaticLayout: true,
                            padding: { top: 12, bottom: 12 },
                            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                            lineNumbersMinChars: 3,
                            glyphMargin: false,
                            folding: true,
                        }}
                        onChange={(value) => onCodeChange?.(value || '')}
                    />
                </div>

                {/* Console Output Area */}
                <div className="w-full md:w-80 flex flex-col bg-black/40 backdrop-blur-md">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/20 border-b border-border/10">
                        <Terminal className="w-3 h-3 text-muted-foreground" />
                        <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Output Console</span>
                    </div>
                    <div className="flex-1 p-3 font-mono text-[10px] overflow-y-auto space-y-1.5 scrollbar-thin">
                        {logs.length === 0 && (
                            <div className="text-muted-foreground/30 italic">No output. Press Run to execute...</div>
                        )}
                        {logs.map((log, i) => (
                            <div key={i} className={cn(
                                "flex gap-2 leading-relaxed break-all",
                                log.type === 'error' ? "text-red-400" :
                                    log.type === 'success' ? "text-green-400" : "text-cyan-100/70"
                            )}>
                                <span className="opacity-30 shrink-0">[{log.time}]</span>
                                <span>{log.msg}</span>
                            </div>
                        ))}
                        <div ref={logEndRef} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MonacoWidget;
