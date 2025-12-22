import React from 'react';
import { Code2, Terminal, Globe, FileCode, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import Editor from "@monaco-editor/react";

export const WorkspacePanel: React.FC = () => {
    const { activeTab, setActiveTab, codeContent, webUrl, logs } = useAppStore();

    const tabs = [
        { id: 'code', label: 'Code', icon: Code2 },
        { id: 'output', label: 'Output', icon: Terminal },
        { id: 'web', label: 'Web', icon: Globe },
        { id: 'html', label: 'Preview', icon: FileCode },
    ] as const;

    return (
        <div className="h-full flex flex-col bg-charcoal-900">
            {/* Tabs Header */}
            <div className="flex items-center border-b border-border bg-background/50">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            "flex items-center gap-2 px-4 py-3 text-xs font-medium border-b-2 transition-all hover:bg-accent/50",
                            activeTab === tab.id
                                ? "border-primary text-primary bg-primary/5"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <tab.icon className="w-3.5 h-3.5" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {activeTab === 'code' && (
                    <Editor
                        height="100%"
                        defaultLanguage="python"
                        theme="vs-dark" // We'll customize this later to match charcoal
                        value={codeContent}
                        options={{
                            minimap: { enabled: false },
                            fontSize: 13,
                            fontFamily: 'JetBrains Mono, Menlo, monospace',
                            scrollBeyondLastLine: false,
                            padding: { top: 16 },
                        }}
                    />
                )}

                {activeTab === 'output' && (
                    <div className="p-4 font-mono text-xs space-y-2 overflow-y-auto h-full">
                        <div className="text-green-400"># System initialized</div>
                        {logs.map((log, i) => (
                            <div key={i} className="border-l-2 border-border pl-2 py-1">
                                <span className="opacity-50 text-[10px] mr-2">{new Date().toLocaleTimeString()}</span>
                                {log}
                            </div>
                        ))}
                        {logs.length === 0 && (
                            <div className="text-muted-foreground italic">No logs yet...</div>
                        )}
                    </div>
                )}

                {activeTab === 'web' && (
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
                )}

                {activeTab === 'html' && (
                    <div className="h-full p-8 flex items-center justify-center text-muted-foreground bg-white/5">
                        <div className="text-center">
                            <FileCode className="w-10 h-10 mx-auto mb-4 opacity-50" />
                            <p>Final HTML Dashboard will render here</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
