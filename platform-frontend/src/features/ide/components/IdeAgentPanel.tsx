import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ArrowRight, User, Bot, Trash2, Quote, ScrollText, MessageSquare, X, ChevronDown, ChevronUp, Sparkles, History, Plus, Clock, Cpu, ChevronRight, FileCode, FileText, File, Copy, Check, ArrowRightToLine, Square, ArrowUp } from 'lucide-react';
import { useAppStore } from '@/store';
import type { FileContext, RAGDocument } from '@/types';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '@/lib/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from '@/components/theme';
import { availableTools, type ToolCall } from '@/lib/agent-tools';

// --- Reused Components (To be extracted later) ---

const CodeBlock = ({ inline, className, children, theme, ideActiveDocumentId, ideOpenDocuments, updateIdeDocumentContent, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const [copied, setCopied] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(false);
    const content = String(children).replace(/\n$/, '');

    const handleCopy = () => {
        navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleInsert = () => {
        // If we have an active document, insert at cursor or append
        // For this simple version, we'll append if `updateIdeDocumentContent` is available
        if (ideActiveDocumentId && updateIdeDocumentContent) {
            updateIdeDocumentContent(ideActiveDocumentId, content, true); // true = append
        } else {
            navigator.clipboard.writeText(content); // Fallback to copy
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    if (inline || !match) {
        return (
            <code className={cn("px-1.5 py-0.5 rounded-md bg-muted/50 font-mono text-[11px] text-primary/80 border border-border/30", className)} {...props}>
                {children}
            </code>
        );
    }

    return (
        <div className={cn(
            "relative group my-4 rounded-lg overflow-hidden border shadow-sm transition-all hover:border-primary/40",
            theme === 'dark'
                ? "bg-black/40 border-border/50 backdrop-blur-sm"
                : "bg-white border-slate-200 shadow-slate-200/60"
        )}>
            <div className={cn(
                "flex items-center justify-between px-3 py-2 border-b cursor-pointer select-none",
                theme === 'dark'
                    ? "bg-muted/40 border-border/30"
                    : "bg-slate-50 border-slate-200"
            )}
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <div className="flex items-center gap-2">
                    <ChevronRight className={cn(
                        "w-3.5 h-3.5 transition-transform duration-200",
                        !isCollapsed ? "rotate-90" : "",
                        theme === 'dark' ? "text-muted-foreground" : "text-slate-500"
                    )} />
                    <span className={cn(
                        "text-[10px] font-bold uppercase tracking-widest",
                        theme === 'dark' ? "text-muted-foreground/80" : "text-slate-600"
                    )}>{match[1]}</span>
                </div>
                <div className="flex items-center gap-1">
                    {!isCollapsed && (
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                            <button
                                onClick={(e) => { e.stopPropagation(); handleInsert(); }}
                                className={cn(
                                    "hover:bg-primary/20 rounded-md transition-all flex items-center gap-1.5 px-2 py-1",
                                    theme === 'dark' ? "text-muted-foreground hover:text-primary" : "text-slate-600 hover:text-primary"
                                )}
                                title="Insert into active file"
                            >
                                <ArrowRightToLine className="w-3.5 h-3.5" />
                                <span className="text-[9px] font-bold">INSERT</span>
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); handleCopy(); }}
                                className={cn(
                                    "hover:bg-primary/20 rounded-md transition-all flex items-center gap-1.5 px-2 py-1",
                                    theme === 'dark' ? "text-muted-foreground hover:text-primary" : "text-slate-600 hover:text-primary"
                                )}
                                title="Copy to clipboard"
                            >
                                {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                                <span className="text-[9px] font-bold">{copied ? 'COPIED' : 'COPY'}</span>
                            </button>
                        </div>
                    )}
                </div>
            </div>
            {!isCollapsed && (
                /* @ts-ignore */
                <SyntaxHighlighter
                    {...props}
                    style={theme === 'dark' ? vscDarkPlus : oneLight}
                    language={match[1]}
                    PreTag="div"
                    className="!bg-transparent !m-0 !p-4 max-h-[500px] overflow-auto scrollbar-thin scrollbar-thumb-primary/20 scrollbar-track-transparent h-full !text-[12px] !leading-relaxed"
                    codeTagProps={{
                        style: {
                            fontFamily: 'JetBrains Mono, Menlo, Courier New, monospace',
                        }
                    }}
                >
                    {content}
                </SyntaxHighlighter>
            )}
        </div>
    );
};

const MessageContent: React.FC<{ content: string, role: 'user' | 'assistant' | 'system' }> = ({ content, role }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const { theme } = useTheme();
    const updateIdeDocumentContent = useAppStore(state => state.updateIdeDocumentContent);
    const ideActiveDocumentId = useAppStore(state => state.ideActiveDocumentId);
    const ideOpenDocuments = useAppStore(state => state.ideOpenDocuments);

    if (role === 'user') {
        const isToolOutput = content.includes('[System Tool Output]');
        if (isToolOutput) {
            const toolResults: { name: string, output: string }[] = [];
            const regex = />?\s*Tool Output \((.*?)\):?\s*?\n+```(?:[\w-]*\n)?([\s\S]*?)```/g;
            let match;
            while ((match = regex.exec(content)) !== null) {
                toolResults.push({ name: match[1].trim(), output: match[2].trim() });
            }

            if (toolResults.length > 0) {
                return (
                    <div className="flex flex-col gap-3 w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
                        {toolResults.map((tr, idx) => (
                            <div key={idx} className="rounded-sm border border-border overflow-hidden bg-card/30 shadow-sm transition-all hover:bg-card/80">
                                <div className="px-3 py-1.5 bg-muted/40 border-b border-border flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className={cn(
                                            "w-1.5 h-1.5 rounded-full shrink-0",
                                            tr.name === 'run_command' ? "bg-green-500 animate-pulse" : "bg-primary"
                                        )} />
                                        <span className="text-[9px] font-bold uppercase tracking-wider opacity-70 truncate max-w-[150px]">
                                            {tr.name.replace(/_/g, ' ')}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <span className="text-[8px] opacity-40 font-mono tracking-tighter">AGENT TOOL OUTPUT</span>
                                    </div>
                                </div>
                                <div className={cn(
                                    "p-3 font-mono text-[11px] overflow-x-auto selection:bg-primary/20",
                                    (tr.name === 'run_command' || tr.name === 'read_terminal') ? "bg-[#1e1e1e] text-[#d4d4d4]" : "text-foreground/85"
                                )}>
                                    <pre className="whitespace-pre-wrap break-words leading-relaxed">{tr.output || <span className="italic opacity-50 px-1">(No output)</span>}</pre>
                                </div>
                            </div>
                        ))}
                    </div>
                );
            }
        }
        return (
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                {content}
            </div>
        );
    }

    if (typeof content !== 'string') {
        return <div className="text-xs text-muted-foreground italic">Invalid message content</div>;
    }

    const thinkMatch = content.match(/<think>([\s\S]*?)(?:<\/think>|$)/);
    const thinking = thinkMatch ? thinkMatch[1].trim() : null;
    const mainAnswer = content.replace(/<think>([\s\S]*?)(?:<\/think>|$)/, '').trim();
    const tokenCount = thinking ? Math.max(1, Math.round(thinking.length / 4)) : 0;

    const markdownComponents = useMemo(() => ({
        code: (props: any) => (
            <CodeBlock
                {...props}
                theme={theme}
                ideActiveDocumentId={ideActiveDocumentId}
                ideOpenDocuments={ideOpenDocuments}
                updateIdeDocumentContent={updateIdeDocumentContent}
            />
        ),
        p: ({ children }: any) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
        ul: ({ children }: any) => <ul className="ml-4 space-y-1 mb-3 list-disc text-sm">{children}</ul>,
        ol: ({ children }: any) => <ol className="ml-4 space-y-1 mb-3 list-decimal text-sm">{children}</ol>,
        li: ({ children }: any) => <li className="leading-relaxed">{children}</li>,
    }), [theme, ideActiveDocumentId, ideOpenDocuments, updateIdeDocumentContent]);

    return (
        <div className="space-y-1 min-w-0">
            {thinking && (
                <div className="mb-2">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground/60 hover:text-foreground transition-colors select-none py-1 group"
                    >
                        <ChevronRight className={cn("w-3.5 h-3.5 transition-transform opacity-50 group-hover:opacity-100", isExpanded ? "rotate-90" : "")} />
                        <span className="font-medium">Thought for ~{tokenCount} tokens</span>
                    </button>
                    {isExpanded && (
                        <div className="mt-2 pl-4 border-l-2 border-primary/20 text-muted-foreground text-xs leading-relaxed animate-in fade-in slide-in-from-top-1">
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{thinking}</ReactMarkdown>
                        </div>
                    )}
                </div>
            )}
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground/90">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{mainAnswer || (thinking ? "" : content)}</ReactMarkdown>
            </div>
        </div>
    );
};

const FilePill: React.FC<{ file: FileContext; onRemove?: () => void }> = ({ file, onRemove }) => {
    const openIdeDocument = useAppStore(state => state.openIdeDocument);

    const getIcon = () => {
        if (file.name.endsWith('.tsx') || file.name.endsWith('.ts')) return <FileCode className="w-3 h-3 text-blue-400" />;
        if (file.name.endsWith('.py')) return <FileCode className="w-3 h-3 text-green-400" />;
        if (file.name.endsWith('.md')) return <FileText className="w-3 h-3 text-purple-400" />;
        return <File className="w-3 h-3 text-muted-foreground" />;
    };

    return (
        <div
            onClick={(e) => {
                e.stopPropagation();
                openIdeDocument({
                    id: file.path,
                    title: file.name,
                    type: file.name.split('.').pop() || 'txt'
                });
            }}
            className="group flex items-center gap-1.5 px-2.5 py-1.5 bg-accent/30 text-foreground text-[10px] font-medium rounded-md border border-border/50 cursor-pointer hover:bg-accent/50 transition-all select-none mb-1 shadow-sm"
        >
            {getIcon()}
            <span className="truncate max-w-[140px]">{file.name}</span>
            {onRemove && (
                <button onClick={(e) => { e.stopPropagation(); onRemove(); }} className="hover:text-destructive transition-colors ml-0.5">
                    <X className="w-3 h-3" />
                </button>
            )}
        </div>
    );
};

const ContextPill: React.FC<{ content: string }> = ({ content }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const { theme } = useTheme();

    const firstLine = content.split('\n')[0].trim();
    const label = firstLine.length > 40 ? firstLine.substring(0, 40) + '...' : firstLine;

    return (
        <div
            onClick={() => setIsExpanded(!isExpanded)}
            className={cn(
                "group flex flex-col gap-1.5 px-3 py-1.5 rounded-md border mb-1 cursor-pointer transition-all",
                theme === 'dark'
                    ? "bg-primary/10 text-primary border-primary/20 hover:bg-primary/20"
                    : "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100 shadow-sm",
                isExpanded ? "w-full max-w-full" : "max-w-fit"
            )}
        >
            <div className="flex items-center gap-2 w-full">
                <Quote className={cn("w-3 h-3 shrink-0", theme === 'dark' ? "opacity-70" : "opacity-90")} />
                <span className={cn("font-semibold truncate text-[10px]", isExpanded && "whitespace-normal")}>
                    {label}
                </span>
                {!isExpanded ? (
                    <ChevronDown className="w-3 h-3 opacity-50 group-hover:opacity-100" />
                ) : (
                    <ChevronUp className="w-3 h-3 opacity-50 group-hover:opacity-100 ml-auto" />
                )}
            </div>
            {isExpanded && (
                <div className={cn(
                    "mt-1 w-full font-mono p-2.5 rounded border whitespace-pre-wrap break-words text-[11px] leading-relaxed animate-in fade-in slide-in-from-top-1 duration-200",
                    theme === 'dark'
                        ? "bg-black/40 text-foreground/90 border-white/10"
                        : "bg-white text-slate-800 border-blue-100 shadow-inner"
                )}>
                    {content}
                </div>
            )}
        </div>
    );
};

export const IdeAgentPanel: React.FC = () => {
    const explorerRootPath = useAppStore(state => state.explorerRootPath);
    const ideProjectChatHistory = useAppStore(state => state.ideProjectChatHistory);
    const chatSessions = useAppStore(state => state.chatSessions);
    const fetchChatSessions = useAppStore(state => state.fetchChatSessions);
    const loadChatSession = useAppStore(state => state.loadChatSession);
    const createNewChatSession = useAppStore(state => state.createNewChatSession);
    const activeChatSessionId = useAppStore(state => state.activeChatSessionId);
    const addMessageToDocChat = useAppStore(state => state.addMessageToDocChat);
    const selectedFileContexts = useAppStore(state => state.selectedFileContexts);
    const addSelectedFileContext = useAppStore(state => state.addSelectedFileContext);
    const removeSelectedFileContext = useAppStore(state => state.removeSelectedFileContext);
    const clearSelectedFileContexts = useAppStore(state => state.clearSelectedFileContexts);
    const selectedContexts = useAppStore(state => state.selectedContexts);
    const removeSelectedContext = useAppStore(state => state.removeSelectedContext);
    const clearSelectedContexts = useAppStore(state => state.clearSelectedContexts);
    const selectedModel = useAppStore(state => state.localModel);
    const setSelectedModel = useAppStore(state => state.setLocalModel);
    const ollamaModels = useAppStore(state => state.ollamaModels);
    const fetchOllamaModels = useAppStore(state => state.fetchOllamaModels);

    const [inputValue, setInputValue] = useState('');
    const [isThinking, setIsThinking] = useState(false);
    const [pastedImage, setPastedImage] = useState<string | null>(null);
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);
    const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
    const thinkingRef = useRef(false);

    const scrollRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const isUserScrolledUp = useRef(false);
    const [isDragging, setIsDragging] = useState(false);
    const abortControllerRef = useRef<AbortController | null>(null);

    const stopAgent = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsThinking(false);
        thinkingRef.current = false;
    };

    // Smart Scroll Logic
    const handleScroll = () => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            // If user is near bottom (within 50px), they are NOT scrolled up
            isUserScrolledUp.current = scrollHeight - scrollTop - clientHeight > 50;
        }
    };

    useEffect(() => {
        if (scrollRef.current && !isUserScrolledUp.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [ideProjectChatHistory, isThinking]);

    const handlePaste = (e: React.ClipboardEvent) => {
        const items = e.clipboardData.items;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                if (blob) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        setPastedImage(event.target?.result as string);
                    };
                    reader.readAsDataURL(blob);
                }
            }
        }
    };

    const handleSend = async (textOverride?: string) => {
        const textToSend = textOverride || inputValue;
        if ((textToSend.trim() || pastedImage)) {
            let fullContent = textToSend;
            if (pastedImage) fullContent += "\n\n[Pasted Image]";

            const msg = {
                id: Date.now().toString(),
                role: 'user' as const,
                content: fullContent,
                timestamp: Date.now(),
                fileContexts: [...selectedFileContexts],
                contexts: [...selectedContexts]
            };

            addMessageToDocChat(explorerRootPath!, msg);
            setInputValue('');
            setPastedImage(null);
            clearSelectedFileContexts();
            clearSelectedContexts();

            callAgent([...ideProjectChatHistory, msg], fullContent);
        }
    };

    // Initial Load
    useEffect(() => {
        if (explorerRootPath) {
            fetchChatSessions('ide', explorerRootPath);
        }
        fetchOllamaModels();
    }, [explorerRootPath, fetchChatSessions, fetchOllamaModels]);

    const executeTool = async (toolCall: ToolCall, projectRoot?: string): Promise<string> => {
        console.log(`[IDE Agent] Executing tool: ${toolCall.name}`, toolCall.arguments);

        const validatePath = (path: string) => {
            if (!projectRoot) return { valid: true, path };
            let fullPath = path;
            if (!path.startsWith('/') && !path.startsWith('C:') && !path.startsWith('file://')) {
                fullPath = `${projectRoot}/${path}`.replace(/\/+/g, '/');
            }
            // Simple security checks
            if (fullPath.includes('/../') || fullPath.endsWith('/..')) return { valid: false, error: "Access denied (..)" };
            if (!fullPath.startsWith(projectRoot)) return { valid: false, error: "Access denied (Outside Project)" };
            return { valid: true, path: fullPath };
        };

        try {
            switch (toolCall.name) {
                case 'read_file': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const res = await window.electronAPI.invoke('fs:readFile', validation.path!);
                    if (res.success) {
                        useAppStore.getState().openIdeDocument({
                            id: validation.path!,
                            title: validation.path!.split('/').pop() || 'Untitled',
                            content: res.content,
                            type: 'file'
                        } as RAGDocument);
                        return res.content;
                    }
                    return `Error: ${res.error}`;
                }

                case 'write_file': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const res = await window.electronAPI.invoke('fs:writeFile', {
                        path: validation.path,
                        content: toolCall.arguments.content
                    });
                    if (res.success) {
                        useAppStore.getState().refreshExplorerFiles();
                        useAppStore.getState().openIdeDocument({
                            id: validation.path!,
                            title: validation.path!.split('/').pop() || 'Untitled',
                            content: toolCall.arguments.content,
                            type: 'file'
                        } as RAGDocument);
                        return `Success: File written to ${validation.path}`;
                    }
                    return `Error: ${res.error}`;
                }

                case 'replace_in_file': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const { target, replacement } = toolCall.arguments;
                    const originalRes = await window.electronAPI.invoke('fs:readFile', validation.path!);
                    if (!originalRes || !originalRes.success) return `Error reading file: ${originalRes?.error || 'Unknown error'}`;

                    if (!originalRes.content.includes(target)) {
                        return "Error: Target text not found in file. Ensure exact match including whitespace.";
                    }

                    // Check for multiple occurrences if needed, usually simple replace is first occurrence
                    // but for safety we might want uniqueness. adapting form DocAssistant logic:
                    if (originalRes.content.indexOf(target) !== originalRes.content.lastIndexOf(target)) {
                        return "Error: Target text is ambiguous (found multiple times). Provide more context.";
                    }

                    const newContent = originalRes.content.replace(target, replacement);
                    const replaceRes = await window.electronAPI.invoke('fs:writeFile', {
                        path: validation.path!,
                        content: newContent
                    });

                    if (replaceRes.success) {
                        useAppStore.getState().refreshExplorerFiles();
                        useAppStore.getState().openIdeDocument({
                            id: validation.path!,
                            title: validation.path!.split('/').pop() || 'Untitled',
                            content: newContent,
                            type: 'file'
                        } as RAGDocument);
                        return `Success: Text replaced in ${validation.path}`;
                    }
                    return `Error writing file: ${replaceRes.error}`;
                }

                case 'list_dir': {
                    const validation = validatePath(toolCall.arguments.path || "./");
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const listRes = await window.electronAPI.invoke('fs:readDir', validation.path);
                    if (!listRes || !listRes.success) return `Error: ${listRes?.error || 'Unknown error'}`;
                    const items = (listRes.files || []).map((f: any) => `${f.type === 'folder' ? '[DIR]' : '[FILE]'} ${f.name}`).join('\n');
                    return items || "Empty directory.";
                }

                case 'find_by_name': {
                    const rootValidation = validatePath(toolCall.arguments.root || "./");
                    if (!rootValidation.valid) return `Error: ${rootValidation.error}`;

                    const findRes = await window.electronAPI.invoke('fs:find', {
                        pattern: toolCall.arguments.pattern, // e.g. "*.py"
                        root: rootValidation.path
                    });
                    if (!findRes || !findRes.success) return `Error: ${findRes?.error || 'Unknown error'}`;
                    return (findRes.files || []).join('\n') || "No matches found.";
                }

                case 'grep_search': {
                    const rootValidation = validatePath(toolCall.arguments.root || "./");
                    if (!rootValidation.valid) return `Error: ${rootValidation.error}`;

                    const grepRes = await window.electronAPI.invoke('fs:grep', {
                        query: toolCall.arguments.query,
                        root: rootValidation.path
                    });
                    if (!grepRes || !grepRes.success) return `Error: ${grepRes?.error || 'Unknown error'}`;
                    return (grepRes.files || []).join('\n') || "No matches found.";
                }

                case 'view_file_outline': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const outlineRes = await window.electronAPI.invoke('fs:viewOutline', validation.path);
                    if (!outlineRes || !outlineRes.success) return `Error: ${outlineRes?.error || 'Unknown error'}`;
                    return outlineRes.outline || "No items found in file.";
                }

                case 'read_terminal': {
                    const termRes = await window.electronAPI.invoke('terminal:read');
                    if (!termRes) return "Error: Failed to read terminal.";
                    return termRes.success ? termRes.content : `Error reading terminal: ${termRes.error}`;
                }

                case 'multi_replace_file_content': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    // Tool arguments usually come as { path, changes: [{target, replacement}] }
                    const changes = toolCall.arguments.changes;
                    if (!changes || !Array.isArray(changes)) return "Error: 'changes' arguments must be an array.";

                    const multiReadRes = await window.electronAPI.invoke('fs:readFile', validation.path!);
                    if (!multiReadRes || !multiReadRes.success) return `Error reading file: ${multiReadRes?.error || 'Unknown error'}`;

                    let currentContent = multiReadRes.content;
                    for (let i = 0; i < changes.length; i++) {
                        const change = changes[i];
                        if (!currentContent.includes(change.target)) {
                            return `Error: Change ${i + 1}/${changes.length} failed. Target text not found.`;
                        }
                        currentContent = currentContent.replace(change.target, change.replacement);
                    }

                    const multiWriteRes = await window.electronAPI.invoke('fs:writeFile', {
                        path: validation.path!,
                        content: currentContent
                    });
                    if (!multiWriteRes.success) return `Error writing file: ${multiWriteRes.error}`;

                    useAppStore.getState().refreshExplorerFiles();
                    useAppStore.getState().openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        content: currentContent,
                        type: 'file'
                    } as RAGDocument);

                    return `Success: Applied ${changes.length} changes to ${validation.path}`;
                }

                case 'run_command': {
                    let cwd = toolCall.arguments.cwd;
                    if (!cwd || cwd.trim() === '.' || cwd.trim() === './') {
                        cwd = projectRoot;
                    } else if (projectRoot && !cwd.startsWith('/') && !cwd.startsWith('C:') && !cwd.startsWith('file://')) {
                        cwd = `${projectRoot}/${cwd}`.replace(/\/+/g, '/');
                    }

                    const res = await window.electronAPI.invoke('shell:exec', {
                        cmd: toolCall.arguments.command,
                        cwd: cwd
                    });
                    if (res.success) {
                        useAppStore.getState().refreshExplorerFiles();
                        if (!res.stdout && !res.stderr) return "Success (No Output)";
                        return `STDOUT:\n${res.stdout}\nSTDERR:\n${res.stderr}`;
                    }
                    return `Error: ${res.error}`;
                }

                default:
                    return `Error: Unknown tool '${toolCall.name}'`;
            }
        } catch (e) {
            return `System Error: ${e}`;
        }
    };

    // Full Implementation of executeTool needed to work
    // I will overwrite `executeTool` above with the COMPLETE one in the actual file write.

    const callAgent = async (currentHistory: any[], userMessage: string | null) => {
        if (!explorerRootPath) return;
        setIsThinking(true);
        thinkingRef.current = true;
        if (abortControllerRef.current) abortControllerRef.current.abort();
        abortControllerRef.current = new AbortController();

        const botMsgId = (Date.now() + Math.random()).toString();
        addMessageToDocChat(explorerRootPath, { id: botMsgId, role: 'assistant', content: '', timestamp: Date.now() });

        let accumulatedContent = '';

        try {
            const payload = {
                query: userMessage || "Continue...",
                history: currentHistory,
                model: selectedModel,
                tools: availableTools,
                project_root: explorerRootPath
            };

            // NEW ENDPOINT
            const response = await fetch(`${API_BASE}/ide/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: abortControllerRef.current.signal
            });

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader!.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.content) {
                                accumulatedContent += data.content;
                                useAppStore.getState().updateMessageContent(explorerRootPath, botMsgId, accumulatedContent);
                            }
                        } catch (e) { }
                    }
                }
            }

            // Tool Execution Logic (Same as before)
            const toolRegex = /```json\s*(\{[\s\S]*?"tool":[\s\S]*?\})\s*```/g;
            let match;
            let toolCalls: ToolCall[] = [];
            while ((match = toolRegex.exec(accumulatedContent)) !== null) {
                try {
                    const jsonCall = JSON.parse(match[1]);
                    toolCalls.push({ name: jsonCall.tool || jsonCall.name, arguments: jsonCall.args || jsonCall.arguments || {} });
                } catch (e) { }
            }

            if (toolCalls.length > 0 && thinkingRef.current) {
                let toolOutputs = "";
                for (const call of toolCalls) {
                    if (!thinkingRef.current) break;
                    // We need the FULL executeTool here. I'll ensure I copy the full helper from DocAssistant.
                    const result = await executeTool(call, explorerRootPath);
                    toolOutputs += `\n\n> Tool Output (${call.name}):\n\`\`\`\n${result}\n\`\`\`\n`;
                }

                if (thinkingRef.current) {
                    const toolMsg = {
                        id: Date.now().toString(),
                        role: 'user' as const,
                        content: `[System Tool Output]:${toolOutputs}`,
                        timestamp: Date.now()
                    };
                    addMessageToDocChat(explorerRootPath, toolMsg);
                    await callAgent([...currentHistory, { role: 'assistant', content: accumulatedContent }, { role: 'user', content: toolMsg.content }], null);
                }
            }

        } catch (e) {
            console.error(e);
        } finally {
            setIsThinking(false);
            thinkingRef.current = false;
        }
    };

    // Render Logic...
    return (
        <div
            className="h-full flex flex-col bg-white dark:bg-card relative"
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
            onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
            onDragLeave={(e) => {
                if (e.currentTarget === e.target) setIsDragging(false);
            }}
            onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsDragging(false);
                const fileData = e.dataTransfer.getData('application/arcturus-file');
                if (fileData) {
                    try {
                        const file = JSON.parse(fileData);
                        if (!selectedFileContexts.some(f => f.path === file.path)) {
                            addSelectedFileContext(file);
                        }
                    } catch (e) { console.error("Drop parse error", e); }
                }
            }}
        >
            {/* Full Panel Drop Overlay */}
            {isDragging && (
                <div className="absolute inset-0 z-[100] bg-primary/5 backdrop-blur-[2px] border-2 border-dashed border-primary/40 rounded-lg flex flex-col items-center justify-center p-8 pointer-events-none animate-in fade-in duration-200">
                    <div className="bg-background/80 p-6 rounded-2xl shadow-2xl flex flex-col items-center gap-4 border border-primary/20 scale-110">
                        <div className="p-4 bg-primary/10 rounded-full">
                            <Plus className="w-8 h-8 text-primary animate-bounce" />
                        </div>
                        <p className="text-sm font-bold text-primary">Drop file to add as context</p>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="px-4 py-3 border-b border-border bg-white/95 dark:bg-card/95 backdrop-blur z-10 flex items-center justify-between">
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className="flex flex-col min-w-0">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">IDE Agent</span>
                        <span className="text-xs font-medium truncate text-foreground">
                            {explorerRootPath?.split('/').pop() || 'No Project'}
                        </span>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={() => {
                            if (explorerRootPath) createNewChatSession('ide', explorerRootPath);
                        }}
                        className="p-2 hover:bg-muted rounded-md text-muted-foreground hover:text-foreground transition-colors"
                        title="New Chat"
                    >
                        <Plus className="w-4 h-4" />
                    </button>

                    <div className="relative history-menu-container">
                        <button
                            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
                            className={cn(
                                "p-2 hover:bg-muted rounded-md transition-colors",
                                isHistoryOpen ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground"
                            )}
                            title="Chat History"
                        >
                            <History className="w-4 h-4" />
                        </button>

                        {isHistoryOpen && (
                            <div className="absolute top-full right-0 mt-2 w-64 bg-background border border-border shadow-xl rounded-lg z-50 p-2 max-h-60 overflow-y-auto">
                                <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest px-2 py-1 mb-1">Previous Chats</p>
                                {chatSessions.length === 0 ? (
                                    <p className="text-xs text-muted-foreground px-2 py-4 text-center italic">No history yet</p>
                                ) : (
                                    chatSessions.map(session => (
                                        <button
                                            key={session.id}
                                            onClick={() => {
                                                if (explorerRootPath) loadChatSession(session.id, 'ide', explorerRootPath);
                                                setIsHistoryOpen(false);
                                            }}
                                            className={cn(
                                                "w-full text-left px-2 py-2 rounded-md hover:bg-muted transition-colors text-xs mb-1 flex items-center justify-between group",
                                                activeChatSessionId === session.id ? "bg-muted" : ""
                                            )}
                                        >
                                            <div className="truncate flex-1 pr-2">
                                                <span className="block truncate font-medium">{session.title}</span>
                                                <span className="block text-[9px] text-muted-foreground flex items-center gap-1 mt-0.5">
                                                    <Clock className="w-2 h-2" />
                                                    {new Date(session.updated_at * 1000).toLocaleDateString()}
                                                </span>
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Chat History */}
            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
            >
                {/* Empty State */}
                {ideProjectChatHistory.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4 py-8">
                        <div className="opacity-50 space-y-2">
                            <Cpu className="w-12 h-12 mx-auto text-primary/50" />
                            <p className="text-sm font-medium">Ready to code.</p>
                            <p className="text-xs text-muted-foreground max-w-[200px]">I have full access to execute commands and read/write files in this project.</p>
                        </div>
                        {/* Quick Actions */}
                        <div className="flex flex-col gap-2 w-full max-w-xs mt-4 animate-in fade-in slide-in-from-bottom-2 duration-500 delay-100">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground opacity-70">Quick Actions</p>
                            <button
                                onClick={() => handleSend('Summarize this project structure and key components.')}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/40 hover:bg-muted rounded-lg text-xs text-foreground transition-all border border-border/50 hover:border-primary/20 text-left"
                            >
                                <ScrollText className="w-4 h-4 text-primary shrink-0" />
                                <span>Summarize Project Structure</span>
                            </button>
                            <button
                                onClick={() => handleSend('What are the key takeaways and main features of this codebase?')}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/40 hover:bg-muted rounded-lg text-xs text-foreground transition-all border border-border/50 hover:border-primary/20 text-left"
                            >
                                <Quote className="w-4 h-4 text-primary shrink-0" />
                                <span>Key Takeaways</span>
                            </button>
                        </div>
                    </div>
                )}

                {ideProjectChatHistory.map((msg) => (
                    <div key={msg.id} className={cn(
                        "flex flex-col w-full mb-6",
                        msg.role === 'user' ? "items-end" : "items-start"
                    )}>
                        {/* Message Header (Role Name) */}
                        {msg.role === 'assistant' && (
                            <div className="flex items-center gap-2 mb-1.5 px-1 opacity-60">
                                <span className="text-[10px] font-bold uppercase tracking-widest">RESPONSE</span>
                            </div>
                        )}

                        <div className={cn(
                            "max-w-full min-w-0 overflow-hidden",
                            msg.role === 'user' ? "max-w-[98%]" : "w-full"
                        )}>
                            {msg.role === 'user' && ((msg.contexts && msg.contexts.length > 0) || (msg.fileContexts && msg.fileContexts.length > 0)) && (
                                <div className="flex flex-col items-end w-full mb-1 space-y-1">
                                    {msg.contexts?.map((ctx: string, idx: number) => (
                                        <ContextPill key={`ctx-${idx}`} content={ctx} />
                                    ))}
                                    {msg.fileContexts?.map((file: any, idx: number) => (
                                        <FilePill key={`file-${idx}`} file={file} />
                                    ))}
                                </div>
                            )}
                            <div className={cn(
                                "text-sm",
                                msg.role === 'user'
                                    ? "bg-white/10 dark:bg-white/5 border border-border/50 text-foreground rounded-lg shadow-sm leading-normal backdrop-blur-sm"
                                    : "text-foreground leading-relaxed"
                            )}>
                                <MessageContent content={msg.content} role={msg.role as any} />
                            </div>
                        </div>
                    </div>
                ))}

                {isThinking && (
                    <div className="flex flex-col w-full mb-4">
                        <div className="flex items-center gap-2 mb-1.5 px-1 opacity-60">
                            <Bot className="w-3 h-3" />
                            <span className="text-[10px] font-bold uppercase tracking-widest">Assistant</span>
                        </div>
                        <div className="pl-1 text-sm text-foreground">
                            <span className="flex items-center gap-2 text-muted-foreground italic text-xs">
                                Thinking <span className="flex gap-1"><span className="animate-bounce">.</span><span className="animate-bounce delay-100">.</span><span className="animate-bounce delay-200">.</span></span>
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-3 border-t border-border/50 bg-background/50 backdrop-blur-sm">
                {/* Image Preview */}
                {pastedImage && (
                    <div className="relative mb-3 inline-block group animate-in fade-in zoom-in duration-200">
                        <img src={pastedImage} alt="Pasted" className="h-20 rounded-lg border border-border shadow-md object-cover" />
                        <button
                            onClick={() => setPastedImage(null)}
                            className="absolute -top-2 -right-2 p-1 bg-destructive text-destructive-foreground rounded-full hover:bg-destructive/90 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                )}

                {/* Context Pills (Text & File) */}
                {(selectedContexts.length > 0 || selectedFileContexts.length > 0) && (
                    <div className="flex flex-wrap gap-2 mb-2 max-h-[100px] overflow-y-auto scrollbar-thin scrollbar-thumb-muted">
                        {/* Text Contexts */}
                        {selectedContexts.map((ctx, i) => (
                            <div key={`text-${i}`} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary text-[10px] font-medium rounded-md max-w-full border border-primary/20 shadow-sm animate-in fade-in slide-in-from-bottom-1">
                                <Quote className="w-3 h-3 shrink-0 opacity-70" />
                                <span className="truncate max-w-[160px]">{ctx.substring(0, 40)}...</span>
                                <button onClick={() => removeSelectedContext(i)} className="hover:text-primary/70 ml-1 transition-colors"><X className="w-3 h-3" /></button>
                            </div>
                        ))}
                        {/* File Contexts */}
                        {selectedFileContexts.map((f, i) => <FilePill key={`file-${i}`} file={f} onRemove={() => removeSelectedFileContext(i)} />)}
                    </div>
                )}

                <div className={cn(
                    "relative bg-muted/40 border border-border/50 rounded-xl focus-within:ring-1 focus-within:ring-primary/20 transition-all shadow-sm",
                    isThinking ? "opacity-80 pointer-events-none" : ""
                )}>
                    <textarea
                        ref={textareaRef}
                        value={inputValue}
                        onChange={e => setInputValue(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={e => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder={selectedContexts.length > 0 ? "Ask about selected text..." : "Ask anything..."}
                        className="w-full bg-transparent p-3 text-sm focus:outline-none resize-none min-h-[40px] max-h-[200px]"
                        rows={1}
                        style={{ height: 'auto', minHeight: '44px' }}
                    />

                    <div className="flex items-center justify-between p-2 border-t border-border/10">
                        {/* Model Selector */}
                        <div className="relative model-menu-container">
                            <button
                                onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
                                className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-background/50 text-[10px] font-medium text-muted-foreground transition-colors border border-transparent hover:border-border/30"
                            >
                                <Cpu className="w-3 h-3" />
                                <span>{ollamaModels.find(m => m.name === selectedModel)?.name || selectedModel}</span>
                                <ChevronDown className="w-3 h-3 opacity-50" />
                            </button>

                            {isModelMenuOpen && (
                                <div className="absolute bottom-full left-0 mb-2 w-48 bg-popover border border-border shadow-xl rounded-lg z-50 overflow-hidden animate-in fade-in slide-in-from-bottom-1 p-1">
                                    <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest px-2 py-1.5">Select Model</p>
                                    {ollamaModels.length === 0 && <p className="px-2 py-2 text-xs text-muted-foreground italic">No models found</p>}
                                    {ollamaModels.map(model => (
                                        <button
                                            key={model.name}
                                            onClick={() => {
                                                setSelectedModel(model.name);
                                                setIsModelMenuOpen(false);
                                            }}
                                            className={cn(
                                                "w-full text-left px-2 py-1.5 rounded-md text-xs flex items-center gap-2 transition-colors",
                                                selectedModel === model.name ? "bg-primary/10 text-primary" : "hover:bg-muted text-foreground"
                                            )}
                                        >
                                            {selectedModel === model.name && <Check className="w-3 h-3 shrink-0" />}
                                            <span className={cn("truncate", selectedModel !== model.name && "pl-5")}>
                                                {model.name}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="flex">
                            {isThinking ? (
                                <button
                                    onClick={stopAgent}
                                    className="p-2 bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 transition-all shadow-sm flex items-center gap-1.5 animate-in fade-in zoom-in duration-200"
                                    title="Stop generating"
                                >
                                    <Square className="w-3.5 h-3.5 fill-current" />
                                </button>
                            ) : (
                                <button
                                    onClick={() => handleSend()}
                                    disabled={!inputValue.trim() && selectedFileContexts.length === 0}
                                    className="p-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <ArrowRight className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );

};
