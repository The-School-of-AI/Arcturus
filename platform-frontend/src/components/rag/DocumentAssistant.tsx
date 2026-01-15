import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Send, User, Bot, Trash2, Quote, ScrollText, MessageSquare, X, ChevronDown, ChevronUp, Sparkles, History, Plus, Clock, Cpu, ChevronRight, FileCode, FileText, File, Copy, Check, ArrowRightToLine, Square, ArrowRight } from 'lucide-react';
import { useAppStore } from '@/store';
import type { FileContext } from '@/types';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '@/lib/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from '@/components/theme';
import { availableTools, type ToolCall } from '@/lib/agent-tools';

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
        if (ideActiveDocumentId) {
            const activeDoc = ideOpenDocuments.find((d: any) => d.id === ideActiveDocumentId);
            if (activeDoc) {
                const newContent = (activeDoc.content || '') + '\n' + content;
                updateIdeDocumentContent(ideActiveDocumentId, newContent, true);
            }
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
            "relative group my-4 rounded-sm overflow-hidden border shadow-xl transition-all hover:border-primary/40",
            theme === 'dark'
                ? "bg-black/40 border-border/50 backdrop-blur-sm selection:bg-primary/30"
                : "bg-white border-slate-300 shadow-slate-200/60 selection:bg-blue-100/80 selection:text-slate-900"
        )}>
            <div className={cn(
                "flex items-center justify-between px-3 py-1.5 border-b cursor-pointer select-none",
                theme === 'dark'
                    ? "bg-muted/40 border-border/30 backdrop-blur-md"
                    : "bg-slate-100 border-slate-300"
            )}
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <div className="flex items-center gap-2">
                    <ChevronRight className={cn(
                        "w-3 h-3 transition-transform duration-200",
                        !isCollapsed ? "rotate-90" : "",
                        theme === 'dark' ? "text-muted-foreground/60" : "text-slate-500"
                    )} />
                    <span className={cn(
                        "text-[10px] font-bold uppercase tracking-[2px]",
                        theme === 'dark' ? "text-muted-foreground/60" : "text-slate-600"
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
                                <ArrowRightToLine className="w-3 h-3" />
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
                                {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                                <span className="text-[9px] font-bold">{copied ? 'COPIED' : 'COPY'}</span>
                            </button>
                        </div>
                    )}
                    {isCollapsed && (
                        <span className="text-[9px] font-medium text-muted-foreground italic px-2">
                            {content.split('\n').length} lines
                        </span>
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
                    className="!bg-transparent !m-0 !p-3 max-h-[500px] overflow-auto scrollbar-thin scrollbar-thumb-primary/20 scrollbar-track-transparent h-full"
                    codeTagProps={{
                        style: {
                            fontSize: '11px',
                            fontFamily: 'JetBrains Mono, Menlo, Courier New, monospace',
                            lineHeight: '1.7',
                            letterSpacing: '-0.3px',
                            color: theme === 'dark' ? undefined : '#24292e'
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
        return (
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                {content}
            </div>
        );
    }

    if (typeof content !== 'string') {
        return <div className="text-xs text-muted-foreground italic">Invalid message content</div>;
    }

    // Handle partial tags during streaming using check for end of string or closing tag
    const thinkMatch = content.match(/<think>([\s\S]*?)(?:<\/think>|$)/);
    const thinking = thinkMatch ? thinkMatch[1].trim() : null;
    const mainAnswer = content.replace(/<think>([\s\S]*?)(?:<\/think>|$)/, '').trim();

    // Calculate approximate tokens (4 chars/token)
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
                        className="flex items-center gap-1.5 text-xs text-muted-foreground/60 hover:text-foreground transition-colors select-none py-1"
                    >
                        <ChevronRight className={cn("w-3.5 h-3.5 transition-transform", isExpanded ? "rotate-90" : "")} />
                        <span className="font-medium">Thought for ~{tokenCount} tokens</span>
                    </button>
                    {isExpanded && (
                        <div className="mt-2 pl-4 border-l-2 border-primary/20 text-muted-foreground text-xs leading-relaxed">
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

const ContextPill: React.FC<{ content: string }> = ({ content }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const { theme } = useTheme();

    // Simple heuristic to get a "label" for the context
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
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        onRemove();
                    }}
                    className="hover:text-destructive transition-colors ml-0.5"
                >
                    <X className="w-3 h-3" />
                </button>
            )}
        </div>
    );
};

export const DocumentAssistant: React.FC = () => {
    const explorerRootPath = useAppStore(state => state.explorerRootPath);
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const ragActiveDocumentId = useAppStore(state => state.ragActiveDocumentId);
    const ragOpenDocuments = useAppStore(state => state.ragOpenDocuments);
    const ideActiveDocumentId = useAppStore(state => state.ideActiveDocumentId);
    const ideOpenDocuments = useAppStore(state => state.ideOpenDocuments);
    const ideProjectChatHistory = useAppStore(state => state.ideProjectChatHistory);
    const chatSessions = useAppStore(state => state.chatSessions);
    const fetchChatSessions = useAppStore(state => state.fetchChatSessions);
    const loadChatSession = useAppStore(state => state.loadChatSession);
    const createNewChatSession = useAppStore(state => state.createNewChatSession);
    const activeChatSessionId = useAppStore(state => state.activeChatSessionId);
    const addMessageToDocChat = useAppStore(state => state.addMessageToDocChat);
    const updateMessageContent = useAppStore(state => state.updateMessageContent);
    const selectedFileContexts = useAppStore(state => state.selectedFileContexts);
    const addSelectedFileContext = useAppStore(state => state.addSelectedFileContext);
    const removeSelectedFileContext = useAppStore(state => state.removeSelectedFileContext);
    const clearSelectedFileContexts = useAppStore(state => state.clearSelectedFileContexts);
    const selectedContexts = useAppStore(state => state.selectedContexts);
    const removeSelectedContext = useAppStore(state => state.removeSelectedContext);
    const clearSelectedContexts = useAppStore(state => state.clearSelectedContexts);
    const selectedModel = useAppStore(state => state.localModel); // For model selection
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

    // Close menus on click away
    useEffect(() => {
        const handleClickAway = (e: MouseEvent) => {
            if (isHistoryOpen || isModelMenuOpen) {
                // Check if we clicked inside a button that toggles them
                const target = e.target as HTMLElement;
                if (!target.closest('.history-menu-container') && !target.closest('.model-menu-container')) {
                    setIsHistoryOpen(false);
                    setIsModelMenuOpen(false);
                }
            }
        };
        document.addEventListener('mousedown', handleClickAway);
        return () => document.removeEventListener('mousedown', handleClickAway);
    }, [isHistoryOpen, isModelMenuOpen]);

    // Determine active document from either RAG or IDE
    const activeDoc = (sidebarTab === 'ide' && ideActiveDocumentId)
        ? ideOpenDocuments?.find(d => d.id === ideActiveDocumentId)
        : ragOpenDocuments.find(d => d.id === ragActiveDocumentId);

    // Fetch sessions and models on mount/doc change
    useEffect(() => {
        const isIde = sidebarTab === 'ide';
        const targetId = isIde ? explorerRootPath : activeDoc?.id;
        if (targetId) {
            fetchChatSessions(isIde ? 'ide' : 'rag', targetId);
        }
        fetchOllamaModels();
    }, [activeDoc?.id, sidebarTab, ideActiveDocumentId, explorerRootPath, fetchChatSessions, fetchOllamaModels]);

    const history = sidebarTab === 'ide' ? ideProjectChatHistory : (activeDoc?.chatHistory || []);

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
    }, [history, isThinking]); // Auto-scroll only if not scrolled up

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

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

    // --- TOOL EXECUTOR ---
    const executeTool = async (toolCall: ToolCall, projectRoot?: string): Promise<string> => {
        console.log(`[Agent] Executing tool: ${toolCall.name}`, toolCall.arguments);

        const validatePath = (path: string) => {
            if (!projectRoot) return { valid: true, path }; // If no root, can't validate (dangerous, but for non-ide chats)

            // Normalize path: if relative, make it absolute under root
            let fullPath = path;
            if (!path.startsWith('/') && !path.startsWith('C:') && !path.startsWith('file://')) {
                fullPath = `${projectRoot}/${path}`.replace(/\/+/g, '/');
            }

            // Security Check: simple string check. In production we'd use path.resolve()
            // But we don't have 'path' module here easily. 
            // We can check if it contains '..' to jump out
            if (fullPath.includes('..')) {
                return { valid: false, error: "Access denied: Path cannot contain '..' to traverse outside project root." };
            }

            if (!fullPath.startsWith(projectRoot)) {
                return { valid: false, error: `Access denied: Path must be within project root (${projectRoot}). Got: ${fullPath}` };
            }

            return { valid: true, path: fullPath };
        };

        try {
            switch (toolCall.name) {
                // --- File System Tools (Electron IPC) ---
                case 'read_file': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const readRes = await window.electronAPI.invoke('fs:readFile', validation.path);
                    if (!readRes) return "Error: Failed to invoke filesystem read.";
                    return readRes.success ? readRes.content : `Error: ${readRes.error}`;
                }

                case 'write_file': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const writeRes = await window.electronAPI.invoke('fs:writeFile', {
                        path: validation.path,
                        content: toolCall.arguments.content
                    });
                    if (!writeRes) return "Error: Failed to invoke filesystem write.";
                    return writeRes.success ? `Success: File written to ${validation.path}` : `Error: ${writeRes.error}`;
                }

                case 'replace_in_file': {
                    const validation = validatePath(toolCall.arguments.path);
                    if (!validation.valid) return `Error: ${validation.error}`;

                    const { target, replacement } = toolCall.arguments;
                    const originalRes = await window.electronAPI.invoke('fs:readFile', validation.path);
                    if (!originalRes || !originalRes.success) return `Error reading file: ${originalRes?.error || 'Unknown error'}`;

                    if (!originalRes.content.includes(target)) {
                        return "Error: Target text not found in file. Please ensure exact match including whitespace.";
                    }

                    if (originalRes.content.indexOf(target) !== originalRes.content.lastIndexOf(target)) {
                        return "Error: Target text is ambiguous (found multiple times). Please provide more context in 'target' to make it unique.";
                    }

                    const newContent = originalRes.content.replace(target, replacement);
                    const replaceRes = await window.electronAPI.invoke('fs:writeFile', {
                        path: validation.path,
                        content: newContent
                    });

                    if (!replaceRes) return "Error: Failed to invoke filesystem write.";
                    return replaceRes.success ? `Success: Text replaced in ${validation.path}` : `Error writing file: ${replaceRes.error}`;
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
                        pattern: toolCall.arguments.pattern,
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

                    const { changes } = toolCall.arguments;
                    const multiReadRes = await window.electronAPI.invoke('fs:readFile', validation.path);
                    if (!multiReadRes || !multiReadRes.success) return `Error reading file: ${multiReadRes?.error || 'Unknown error'}`;

                    let currentContent = multiReadRes.content;
                    for (const change of changes) {
                        if (!currentContent.includes(change.target)) {
                            return `Error: Target text '${change.target.substring(0, 20)}...' not found. Aborting ALL changes.`;
                        }
                        currentContent = currentContent.replace(change.target, change.replacement);
                    }

                    const multiWriteRes = await window.electronAPI.invoke('fs:writeFile', {
                        path: validation.path,
                        content: currentContent
                    });
                    if (!multiWriteRes) return "Error: Failed to invoke filesystem write.";
                    return multiWriteRes.success ? `Success: Applied ${changes.length} changes to ${validation.path}` : `Error writing file: ${multiWriteRes.error}`;
                }

                case 'run_command': {
                    const cmdRes = await window.electronAPI.invoke('shell:exec', {
                        cmd: toolCall.arguments.command,
                        cwd: toolCall.arguments.cwd || projectRoot
                    });
                    if (!cmdRes) return "Error: Failed to execute command.";
                    return cmdRes.success ? `STDOUT:\n${cmdRes.stdout}\nSTDERR:\n${cmdRes.stderr}` : `Execution Error: ${cmdRes.error}`;
                }

                // --- Search Tools (Backend API) ---
                case 'search_web': {
                    const searchRes = await fetch(`${API_BASE}/agent/search`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: toolCall.arguments.query })
                    });
                    const searchData = await searchRes.json();
                    return JSON.stringify(searchData, null, 2);
                }

                case 'read_url': {
                    const urlRes = await fetch(`${API_BASE}/agent/read_url`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: toolCall.arguments.url })
                    });
                    const urlData = await urlRes.json();
                    return JSON.stringify(urlData, null, 2);
                }

                default:
                    return `Error: Unknown tool '${toolCall.name}'`;
            }
        } catch (e) {
            return `System Error executing tool: ${e}`;
        }
    };

    const callAgent = async (targetId: string, currentHistory: any[], userMessage: string | null, image: string | null) => {
        setIsThinking(true);
        thinkingRef.current = true;

        // Abort previous request if any
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        const botMsgId = (Date.now() + Math.random()).toString();
        const botMsg = { id: botMsgId, role: 'assistant' as const, content: '', timestamp: Date.now() };
        addMessageToDocChat(targetId, botMsg);

        let accumulatedContent = '';

        try {
            const payload = {
                docId: targetId,
                query: userMessage || "Continue process...",
                history: currentHistory,
                image: image,
                model: selectedModel,
                tools: availableTools,
                project_root: explorerRootPath // Add this back
            };

            const response = await fetch(`${API_BASE}/rag/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: abortControllerRef.current.signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.content) {
                                accumulatedContent += data.content;
                                useAppStore.getState().updateMessageContent(targetId, botMsgId, accumulatedContent);
                            }
                            if (data.error) {
                                throw new Error(data.error);
                            }
                        } catch (e) { }
                    }
                }
            }

            // 4. Tool Detection & Recursion
            const toolRegex = /```json\s*(\{[\s\S]*?"tool":[\s\S]*?\})\s*```/g;
            let match;
            let toolCalls: ToolCall[] = [];

            while ((match = toolRegex.exec(accumulatedContent)) !== null) {
                try {
                    const jsonCall = JSON.parse(match[1]);
                    const toolName = jsonCall.tool || jsonCall.name; // Defensive
                    if (toolName) {
                        toolCalls.push({
                            name: toolName,
                            arguments: jsonCall.args || jsonCall.arguments || {}
                        });
                    }
                } catch (e) {
                    console.error("Failed to parse tool call", e);
                }
            }

            if (toolCalls.length > 0) {
                if (!thinkingRef.current) return; // Stopped

                let toolOutputs = "";
                for (const call of toolCalls) {
                    const result = await executeTool(call, explorerRootPath || undefined);
                    toolOutputs += `\n\n> Tool Output (${call.name}):\n\`\`\`\n${result}\n\`\`\`\n`;
                }

                const toolOutputMsg = {
                    id: (Date.now() + Math.random()).toString(),
                    role: 'user' as const,
                    content: `[System Tool Output]:${toolOutputs}\n\nPlease proceed with this information.`,
                    timestamp: Date.now()
                };

                const newHistory = [
                    ...currentHistory,
                    { role: 'assistant', content: accumulatedContent },
                    { role: 'user', content: toolOutputMsg.content }
                ];

                await callAgent(targetId, newHistory, null, null);
            }

        } catch (e: any) {
            if (e.name === 'AbortError') {
                console.log("Agent request aborted");
                return;
            }
            console.error("Agent Error:", e);
            addMessageToDocChat(targetId, {
                ...botMsg,
                content: (accumulatedContent || '') + "\n\n⚠️ Error during generation: " + e.message
            });
        } finally {
            abortControllerRef.current = null;
            setIsThinking(false);
            thinkingRef.current = false;
        }
    };

    const handleSend = async () => {
        const isIde = sidebarTab === 'ide';
        const targetId = isIde ? explorerRootPath : activeDoc?.id;
        if ((!inputValue.trim() && !pastedImage && selectedFileContexts.length === 0) || !targetId) return;

        // Combine all selected text contexts
        let contextString = selectedContexts.length > 0
            ? `Context extracts from document:\n${selectedContexts.map(c => `> ${c}`).join('\n\n')}\n\n`
            : '';

        // Add file contexts
        if (selectedFileContexts.length > 0) {
            contextString += "Attached File Contents:\n";
            for (const file of selectedFileContexts) {
                try {
                    const res = await window.electronAPI.invoke('fs:readFile', file.path);
                    if (res.success) {
                        contextString += `\n--- FILE: ${file.name} ---\n${res.content}\n--- END FILE ---\n`;
                    }
                } catch (e) {
                    console.error(`Failed to read file ${file.path}`, e);
                }
            }
        }

        // SPECIAL CASE: For Summarize/Key Takeaways, fetch FULL chunks
        if (inputValue.includes("Summarize") || inputValue.includes("Key Takeaways") || inputValue.includes("takeaways")) {
            try {
                // If IDE mode, we might want to fetch project summary, but for now we keep it doc-based if activeDoc exists
                const path = activeDoc?.id || explorerRootPath;
                if (path) {
                    const res = await fetch(`${API_BASE}/rag/document_chunks?path=${encodeURIComponent(path)}`);
                    const data = await res.json();
                    if (data.status === 'success' && data.markdown) {
                        // Limit context to ~30k chars to avoid token limits (adjust based on model)
                        const chunks = data.markdown.slice(0, 30000);
                        contextString += `\n\nFULL DOCUMENT CONTENT (Truncated to first 30k chars):\n${chunks}\n\n`;
                    }
                }
            } catch (e) {
                console.error("Failed to fetch full context", e);
            }
        }

        const userMsgId = Date.now().toString();
        const userMsg = {
            id: userMsgId,
            role: 'user' as const,
            content: inputValue + (pastedImage ? "\n\n[Pasted Image]" : ""),
            contexts: [...selectedContexts],
            fileContexts: [...selectedFileContexts],
            timestamp: Date.now()
        };

        const fullMessage = contextString + `User Question: ${inputValue}`;

        // Add User Message
        addMessageToDocChat(targetId, userMsg);

        // Reset UI
        setInputValue('');
        setPastedImage(null);
        clearSelectedContexts();
        clearSelectedFileContexts();
        isUserScrolledUp.current = false;

        // Current Chat History including this new message? 
        // No, callAgent appends this one. But we passed `history` which is PREVIOUS history.
        // So we need to append the user message to history effectively.
        // `history` variable comes from store which might not have updated yet.
        // So we manually append.
        const currentHistory = [
            ...history,
            { role: 'user', content: fullMessage } // Enhanced context message
        ];

        // Trigger Agent Loop
        callAgent(targetId, currentHistory, fullMessage, pastedImage);
    };

    if (!activeDoc && !(sidebarTab === 'ide' && explorerRootPath)) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 bg-white dark:bg-card text-center space-y-4">
                <div className="p-4 rounded-full bg-slate-100 dark:bg-white/5">
                    <ScrollText className="w-8 h-8 text-muted-foreground opacity-20" />
                </div>
                <div className="space-y-1">
                    <h3 className="font-bold text-foreground">{sidebarTab === 'ide' ? 'Project Assistant' : 'Document Assistant'}</h3>
                    <p className="text-xs text-muted-foreground">
                        {sidebarTab === 'ide'
                            ? 'Open a project to start an interactive deep-dive into your codebase.'
                            : 'Select a document from the library to start an interactive deep-dive.'}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div
            className="h-full flex flex-col bg-white dark:bg-card relative"
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
            onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
            onDragLeave={(e) => {
                // Only stop if we leave the main container, not just its children
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
            {/* Header: Minimal */}
            <div className="px-4 py-3 border-b border-border bg-white/95 dark:bg-card/95 backdrop-blur z-10 flex items-center justify-between">
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className="flex flex-col min-w-0">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Chat</span>
                        <span className="text-xs font-medium truncate text-foreground">
                            {sidebarTab === 'ide'
                                ? (explorerRootPath?.split('/').pop() || 'Project')
                                : activeDoc?.title}
                        </span>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={() => {
                            const isIde = sidebarTab === 'ide';
                            const targetId = isIde ? explorerRootPath : activeDoc?.id;
                            if (targetId) createNewChatSession(isIde ? 'ide' : 'rag', targetId);
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
                                                const isIde = sidebarTab === 'ide';
                                                const targetId = isIde ? explorerRootPath : activeDoc?.id;
                                                if (targetId) loadChatSession(session.id, isIde ? 'ide' : 'rag', targetId);
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

                    <div className="w-px h-4 bg-border mx-1" />

                    <button
                        onClick={() => useAppStore.getState().clearSelection()}
                        className="p-2 hover:bg-destructive/10 rounded-md text-muted-foreground hover:text-destructive transition-colors"
                        title="Close Panel"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Chat History */}
            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
            >
                {history.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4 py-8">
                        <div className="opacity-50 space-y-2">
                            <Bot className="w-8 h-8 mx-auto" />
                            <p className="text-xs">Ask anything about this {sidebarTab === 'ide' ? 'project' : 'document'}.<br />Selected text will be added as context automatically.</p>
                        </div>

                        {/* Quick Actions */}
                        <div className="flex flex-col gap-2 w-full max-w-xs mt-4">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Quick Actions</p>
                            <button
                                onClick={() => {
                                    setInputValue('Summarize this document in 3-5 concise bullet points');
                                    setTimeout(handleSend, 100);
                                }}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 hover:bg-muted rounded-lg text-sm text-foreground transition-all border border-border/50 hover:border-primary/30"
                            >
                                <ScrollText className="w-4 h-4 text-primary" />
                                Summarize Document
                            </button>
                            <button
                                onClick={() => {
                                    setInputValue('Extract the key takeaways and insights from this document. Focus on actionable points.');
                                    setTimeout(handleSend, 100);
                                }}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 hover:bg-muted rounded-lg text-sm text-foreground transition-all border border-border/50 hover:border-primary/30"
                            >
                                <Quote className="w-4 h-4 text-primary" />
                                Key Takeaways
                            </button>
                        </div>
                    </div>
                )}

                {history.map((msg) => (
                    <div key={msg.id} className={cn(
                        "flex flex-col w-full mb-6", // Added mb-6 for better spacing between turns
                        msg.role === 'user' ? "items-end" : "items-start"
                    )}>
                        {/* Message Header (Role Name) - Optional, maybe just for Bot */}
                        {msg.role === 'assistant' && (
                            <div className="flex items-center gap-2 mb-1.5 px-1 opacity-60">
                                <span className="text-[10px] font-bold uppercase tracking-widest">RESPONSE</span>
                            </div>
                        )}

                        <div
                            className={cn(
                                "max-w-full min-w-0 overflow-hidden",
                                msg.role === 'user' ? "max-w-[85%]" : "w-full" // User gets bubble limit, Bot gets full width
                            )}
                        >
                            {msg.role === 'user' && ((msg.contexts && msg.contexts.length > 0) || (msg.fileContexts && msg.fileContexts.length > 0)) && (
                                <div className="flex flex-col items-end w-full mb-1 space-y-1">
                                    {msg.contexts?.map((ctx, idx) => (
                                        <ContextPill key={`ctx-${idx}`} content={ctx} />
                                    ))}
                                    {msg.fileContexts?.map((file, idx) => (
                                        <FilePill key={`file-${idx}`} file={file} />
                                    ))}
                                </div>
                            )}
                            <div className={cn(
                                "text-sm",
                                msg.role === 'user'
                                    ? "bg-white/10 border border-input text-foreground py-2.5 px-4 rounded-sm shadow-md leading-normal" // User Bubble: Matches input box
                                    : "text-foreground leading-relaxed pl-1" // Bot: minimal/no style
                            )}>
                                <MessageContent content={msg.content} role={msg.role} />
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
                            {/* Simple pulse for "Thinking..." state before we have content */}
                            <span className="flex items-center gap-2 text-muted-foreground italic text-xs">
                                Thinking <span className="flex gap-1"><span className="animate-bounce">.</span><span className="animate-bounce delay-100">.</span><span className="animate-bounce delay-200">.</span></span>
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area: Redesigned */}
            <div className="p-2 bg-background border-t border-border">
                {/* Image Preview */}
                {pastedImage && (
                    <div className="relative mb-3 inline-block group">
                        <img src={pastedImage} alt="Pasted" className="h-24 rounded-lg border border-border shadow-md" />
                        <button
                            onClick={() => setPastedImage(null)}
                            className="absolute -top-2 -right-2 p-1 bg-destructive text-destructive-foreground rounded-full hover:bg-destructive/90 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                )}

                {/* File Context Pills */}
                {(selectedContexts.length > 0 || selectedFileContexts.length > 0) && (
                    <div className="flex flex-wrap gap-2 mb-3 items-start">
                        {/* Text Contexts */}
                        {selectedContexts.map((ctx, i) => (
                            <div key={`text-${i}`} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary text-[10px] font-medium rounded-md max-w-full border border-primary/20 shadow-sm">
                                <Quote className="w-3 h-3 shrink-0 opacity-70" />
                                <span className="truncate max-w-[160px]">{ctx.substring(0, 40)}...</span>
                                <button onClick={() => removeSelectedContext(i)} className="hover:text-primary/70 ml-1 transition-colors"><X className="w-3 h-3" /></button>
                            </div>
                        ))}
                        {/* File Contexts */}
                        {selectedFileContexts.map((file, i) => (
                            <FilePill key={`file-${i}`} file={file} onRemove={() => removeSelectedFileContext(i)} />
                        ))}
                    </div>
                )}

                {/* Main Input Box */}
                <div className="w-full bg-muted/30 border border-input rounded-xl focus-within:ring-1 focus-within:ring-ring focus-within:border-primary/50 transition-all shadow-sm">
                    {/* Top Row: User Chat Input */}
                    <textarea
                        ref={textareaRef}
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onPaste={handlePaste}
                        placeholder={selectedContexts.length > 0 ? "Ask about selected text..." : "Ask a question..."}
                        className="w-full bg-transparent text-foreground placeholder:text-muted-foreground border-none rounded-t-xl px-2 py-2 text-sm focus:outline-none resize-none min-h-[50px] max-h-[160px]"
                        style={{
                            height: 'auto',
                            overflow: inputValue.split('\n').length > 5 ? 'auto' : 'hidden'
                        }}
                        rows={1}
                        onInput={(e) => {
                            const target = e.target as HTMLTextAreaElement;
                            target.style.height = 'auto';
                            target.style.height = `${target.scrollHeight}px`;
                        }}
                    />

                    {/* Bottom Row: Controls */}
                    <div className="flex items-center justify-between px-2 py-1 border-t border-border/40 bg-muted/20 rounded-b-xl">
                        <div className="flex items-center gap-2 model-menu-container">
                            <div className="relative">
                                <button
                                    onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
                                    className="h-7 px-2 flex items-center gap-2 text-[10px] font-medium bg-background border border-border rounded-sm hover:border-primary/50 text-muted-foreground hover:text-foreground transition-all"
                                >
                                    <span>{selectedModel}</span>
                                    <ChevronDown className={cn("w-3 h-3 transition-transform", isModelMenuOpen && "rotate-180")} />
                                </button>

                                {isModelMenuOpen && (
                                    <div className="absolute bottom-full left-0 mb-2 w-56 bg-background border border-border shadow-xl rounded-lg z-50 p-1 animate-in fade-in slide-in-from-bottom-2 duration-200">
                                        <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest px-2 py-1.5 mb-1 opacity-50">Select Local Model</p>
                                        <div className="max-h-64 overflow-y-auto">
                                            {ollamaModels.length === 0 ? (
                                                <p className="text-[10px] text-muted-foreground p-2 text-center italic">No models found</p>
                                            ) : (
                                                ollamaModels.map(opt => (
                                                    <button
                                                        key={opt.name}
                                                        onClick={() => {
                                                            setSelectedModel(opt.name);
                                                            setIsModelMenuOpen(false);
                                                        }}
                                                        className={cn(
                                                            "w-full text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors text-[11px] flex items-center justify-between group",
                                                            selectedModel === opt.name ? "text-primary bg-primary/5" : "text-foreground/80"
                                                        )}
                                                    >
                                                        <div className="flex flex-col">
                                                            <span className="font-medium">{opt.name}</span>
                                                            <span className="text-[9px] opacity-50">{opt.size_gb}GB</span>
                                                        </div>
                                                        {selectedModel === opt.name && <div className="w-1 h-1 rounded-full bg-primary" />}
                                                    </button>
                                                ))
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            {/* Stop Button (Only when thinking) */}
                            {isThinking && (
                                <button
                                    onClick={stopAgent}
                                    className="p-2 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 transition-all flex items-center justify-center"
                                    title="Stop Agent"
                                >
                                    <Square className="w-4 h-4 fill-current" />
                                </button>
                            )}

                            {/* Send Button */}
                            <button
                                onClick={handleSend}
                                disabled={(!inputValue.trim() && !pastedImage && selectedFileContexts.length === 0) || isThinking}
                                className={cn(
                                    "p-2 rounded-lg transition-all flex items-center justify-center",
                                    (inputValue.trim() || pastedImage || selectedFileContexts.length > 0) && !isThinking
                                        ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm scale-100"
                                        : "bg-transparent text-muted-foreground/40 scale-95 cursor-not-allowed"
                                )}
                            >
                                <ArrowRight className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
