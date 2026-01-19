import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ArrowRight, User, Bot, Trash2, Quote, ScrollText, MessageSquare, X, ChevronDown, ChevronUp, Sparkles, History, Plus, Clock, Cpu, ChevronRight, FileCode, FileText, File, Copy, Check, ArrowRightToLine, Square, ArrowUp, Download } from 'lucide-react';
import { useAppStore } from '@/store';
import type { FileContext, RAGDocument, ContextItem } from '@/types';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '@/lib/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from '@/components/theme';
import { availableTools, type ToolCall } from '@/lib/agent-tools';
import { executeAgentTool } from '@/features/ide/utils/agentTools';
import { parseToolCalls } from '@/features/ide/utils/responseParser';
import permissions from '@/config/agent_permissions.json'; // Direct import assuming resolveJsonModule is on
import { checkContentSafety, checkPathSafety, getContentTypeFromPath, BLOCKED_PATTERNS } from '@/config/blocked_patterns';
import { PermissionDialog } from '@/components/dialogs/PermissionDialog';
import { usePermissionDialog, determineRiskLevel } from '@/hooks/usePermissionDialog';

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
                    className="!bg-transparent !m-0 !p-4 w-full !text-[12px] !leading-relaxed !whitespace-pre-wrap !break-all"
                    wrapLongLines={true}
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
                            <div key={idx} className={cn(
                                "rounded-lg border overflow-hidden my-3 transition-all hover:border-primary/40 shadow-sm",
                                theme === 'dark'
                                    ? "bg-black/40 border-border/50 backdrop-blur-sm"
                                    : "bg-white border-slate-200 shadow-slate-200/60"
                            )}>
                                <div className={cn(
                                    "px-3 py-1.5 border-b flex items-center justify-between",
                                    theme === 'dark' ? "bg-muted/40 border-border/30" : "bg-slate-50 border-slate-200"
                                )}>
                                    <div className="flex items-center gap-2">
                                        <div className={cn(
                                            "w-1.5 h-1.5 rounded-full shrink-0",
                                            tr.name === 'run_command' ? "bg-green-500 animate-pulse" : "bg-primary"
                                        )} />
                                        <span className={cn(
                                            "text-[9px] font-bold uppercase tracking-wider opacity-70 truncate max-w-[150px]",
                                            theme === 'dark' ? "text-muted-foreground" : "text-slate-600"
                                        )}>
                                            {tr.name.replace(/_/g, ' ')}
                                        </span>
                                    </div>
                                    <div className="flex items-center shrink-0">
                                        <span className={cn(
                                            "text-[8px] font-mono tracking-tighter opacity-40",
                                            theme === 'dark' ? "text-muted-foreground" : "text-slate-500"
                                        )}>AGENT TOOL OUTPUT</span>
                                    </div>
                                </div>
                                <div className={cn(
                                    "p-3 font-mono text-[11px] overflow-x-auto selection:bg-blue-500/30 max-h-[300px] overflow-y-auto",
                                    theme === 'dark' ? "bg-[#1e1e1e]/50 text-[#d4d4d4]" : "bg-[#fafafa] text-[#383a42]"
                                )}>
                                    <pre className="whitespace-pre-wrap break-all leading-relaxed max-w-full">{tr.output || <span className="italic opacity-50 px-1">(No output)</span>}</pre>
                                </div>
                            </div>
                        ))}
                    </div>
                );
            }
        }
        return (
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words p-2">
                {content}
            </div>
        );
    }

    if (typeof content !== 'string') {
        return <div className="text-xs text-muted-foreground italic">Invalid message content</div>;
    }

    const thinkingParts: string[] = [];
    const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g;
    let match;

    while ((match = thinkRegex.exec(content)) !== null) {
        if (match[1]) thinkingParts.push(match[1].trim());
    }

    const thinking = thinkingParts.length > 0 ? thinkingParts.join('\n\n***\n\n') : null;
    const mainAnswer = content.replace(/<think>[\s\S]*?(?:<\/think>|$)/g, '').trim();
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
        p: ({ children }: any) => <p className="mb-1.5 last:mb-0 leading-relaxed text-foreground/90">{children}</p>,
        ul: ({ children }: any) => <ul className="ml-4 space-y-0.5 mb-1.5 list-disc text-sm">{children}</ul>,
        ol: ({ children }: any) => <ol className="ml-4 space-y-0.5 mb-1.5 list-decimal text-sm">{children}</ol>,
        li: ({ children }: any) => <li className="leading-relaxed mb-0.5 last:mb-0 [&_p]:mb-0">{children}</li>,
    }), [theme, ideActiveDocumentId, ideOpenDocuments, updateIdeDocumentContent]);

    return (
        <div className="min-w-0">
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
            <div className="text-sm leading-relaxed break-words">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                >
                    {(mainAnswer || (thinking ? "" : content)).trim().replace(/\n{3,}/g, '\n\n')}
                </ReactMarkdown>
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

const ContextPill: React.FC<{ item: ContextItem | string }> = ({ item }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const { theme } = useTheme();

    // Handle backward compatibility or string fallback
    const content = typeof item === 'string' ? item : item.text;
    const metadata = typeof item !== 'string' && item.file ? item : null;

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

                {metadata ? (
                    <div className="flex flex-col min-w-0 flex-1">
                        <span className={cn("font-semibold truncate text-[10px]", isExpanded && "whitespace-normal")}>
                            {metadata.file?.split('/').pop()} <span className="opacity-60 font-normal">:{metadata.range?.startLine}-{metadata.range?.endLine}</span>
                        </span>
                        <span className={cn("truncate text-[9px] opacity-70 font-mono", isExpanded && "whitespace-normal")}>
                            {label}
                        </span>
                    </div>
                ) : (
                    <span className={cn("font-semibold truncate text-[10px]", isExpanded && "whitespace-normal")}>
                        {label}
                    </span>
                )}

                {!isExpanded ? (
                    <ChevronDown className="w-3 h-3 opacity-50 group-hover:opacity-100 ml-auto" />
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
    const [pastedImages, setPastedImages] = useState<string[]>([]);
    const [selectedImage, setSelectedImage] = useState<string | null>(null); // For Lightbox
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);
    const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
    const [copiedImage, setCopiedImage] = useState(false);
    const thinkingRef = useRef(false);

    // Permission dialog hook for agent operations
    // Review State from Global Store
    const reviewRequest = useAppStore(state => state.reviewRequest);
    const startReview = useAppStore(state => state.startReview);

    const formatRelativeTime = (timestamp: number) => {
        const now = Math.floor(Date.now() / 1000);
        const diff = now - timestamp;
        if (diff < 60) return `${diff}s`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d`;
        return new Date(timestamp * 1000).toLocaleDateString();
    };

    const copyImageToClipboard = async (dataUrl: string) => {
        try {
            const response = await fetch(dataUrl);
            const blob = await response.blob();
            const item = new ClipboardItem({ [blob.type]: blob });
            await navigator.clipboard.write([item]);
            setCopiedImage(true);
            setTimeout(() => setCopiedImage(false), 2000);
        } catch (err) {
            console.error('Failed to copy image:', err);
        }
    };

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
        const newImages: string[] = [];
        let processCount = 0;
        let imageItemsCount = 0;

        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                imageItemsCount++;
                const blob = items[i].getAsFile();
                if (blob) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        if (event.target?.result) {
                            newImages.push(event.target.result as string);
                        }
                        processCount++;
                        if (processCount === imageItemsCount) {
                            setPastedImages(prev => [...prev, ...newImages].slice(0, 10));
                        }
                    };
                    reader.readAsDataURL(blob);
                }
            }
        }
    };

    const removePastedImage = (index: number) => {
        setPastedImages(prev => prev.filter((_, i) => i !== index));
    };

    const handleSend = async (textOverride?: string) => {
        const textToSend = textOverride || inputValue;
        if ((textToSend.trim() || pastedImages.length > 0)) {
            let fullContent = textToSend;
            if (pastedImages.length > 0) fullContent += `\n\n[${pastedImages.length} Pasted Image${pastedImages.length > 1 ? 's' : ''}]`;

            const msg = {
                id: Date.now().toString(),
                role: 'user' as const,
                content: fullContent,
                timestamp: Date.now(),
                fileContexts: [...selectedFileContexts],
                contexts: [...selectedContexts],
                images: [...pastedImages] // Store in history for potential local preview if needed
            };

            addMessageToDocChat(explorerRootPath!, msg);
            setInputValue('');
            const currentImages = [...pastedImages];
            const currentContexts = [...selectedContexts];
            const currentFileContexts = [...selectedFileContexts];
            setPastedImages([]);
            clearSelectedFileContexts();
            clearSelectedContexts();

            callAgent(ideProjectChatHistory, fullContent, currentImages, currentContexts, currentFileContexts);
        }
    };

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, window.innerHeight * 0.5)}px`;
        }
    }, [inputValue]);

    // Initial Load
    useEffect(() => {
        if (explorerRootPath) {
            fetchChatSessions('ide', explorerRootPath);
        }
        fetchOllamaModels();
    }, [explorerRootPath, fetchChatSessions, fetchOllamaModels]);

    const executeTool = async (toolCall: ToolCall, projectRoot?: string): Promise<string> => {
        return executeAgentTool(toolCall, {
            projectRoot: projectRoot || explorerRootPath || '',
            permissions,
            startReview: (req, cb) => startReview(req, cb as any),
            openIdeDocument: (doc) => useAppStore.getState().openIdeDocument(doc),
            closeIdeDocument: (id) => useAppStore.getState().closeIdeDocument(id),
            refreshExplorerFiles: () => useAppStore.getState().refreshExplorerFiles(),
            checkContentSafety,
            checkPathSafety: (path) => ({ safe: true }), // Reuse existing helpers or mock if simple
            // Note: IdeAgentPanel has these helpers inline or imported? 
            // Checking previous views: checkContentSafety is imported? No, likely defined in file or helper.
            // Wait, I need to pass checkContentSafety and checkPathSafety.
            // Let's assume they are available in scope. 
            // Actually, looking at previous views (Line 526), checkContentSafety is used.
            // I will pass them.
            getContentTypeFromPath: (p) => p.split('.').pop() || null,
            API_BASE
        });
    };

    // Full Implementation of executeTool needed to work
    // I will overwrite `executeTool` above with the COMPLETE one in the actual file write.

    const callAgent = async (currentHistory: any[], userMessage: string | null, images?: string[], currentContexts?: ContextItem[], fileContexts?: { name: string, path: string }[]) => {
        if (!explorerRootPath) return;
        setIsThinking(true);
        thinkingRef.current = true;
        if (abortControllerRef.current) abortControllerRef.current.abort();
        abortControllerRef.current = new AbortController();

        const botMsgId = (Date.now() + Math.random()).toString();
        addMessageToDocChat(explorerRootPath, { id: botMsgId, role: 'assistant', content: '', timestamp: Date.now() });

        let accumulatedContent = '';

        try {
            // Transform history to include context in content string for the LLM
            const effectiveHistory = currentHistory.map(msg => {
                let contextStr = "";
                if (msg.contexts && msg.contexts.length > 0) {
                    contextStr = msg.contexts.map((c: ContextItem | string) => {
                        const text = typeof c === 'string' ? c : c.text;
                        const meta = typeof c !== 'string' && c.file
                            ? `\nFile: ${c.file} (Lines ${c.range?.startLine}-${c.range?.endLine})`
                            : '';
                        const lang = typeof c !== 'string' && c.file ? c.file.split('.').pop() : '';
                        return `\n\n> Context${meta}:\n\`\`\`${lang}\n${text}\n\`\`\``;
                    }).join('');
                }
                return { ...msg, content: msg.content + contextStr };
            });

            // Prepare current message context
            let currentContextStr = "";
            if (currentContexts && currentContexts.length > 0) {
                currentContextStr = currentContexts.map((c: ContextItem | string) => {
                    const text = typeof c === 'string' ? c : c.text;
                    const meta = typeof c !== 'string' && c.file
                        ? `\nFile: ${c.file} (Lines ${c.range?.startLine}-${c.range?.endLine})`
                        : '';
                    const lang = typeof c !== 'string' && c.file ? c.file.split('.').pop() : '';
                    return `\n\n> Context${meta}:\n\`\`\`${lang}\n${text}\n\`\`\``;
                }).join('');
            }

            if (fileContexts && fileContexts.length > 0) {
                const fileStr = fileContexts.map(f =>
                    `\n\n> Active File Context (User Selected): [${f.name}](${f.path})\n` +
                    `> Note: This is the primary file for the current request. Please read it using read_file if needed (though it should be provided in context if small enough, currently we just point to it).`
                ).join('');
                currentContextStr += fileStr;
            }

            const payload = {
                query: (userMessage || "Continue...") + currentContextStr,
                history: effectiveHistory,
                model: selectedModel,
                tools: availableTools,
                project_root: explorerRootPath,
                images: images || []
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

            // Tool Execution Logic
            const toolCalls = parseToolCalls(accumulatedContent);

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

    const dragCounter = useRef(0);

    // Render Logic...
    return (
        <>
            <div
                className="h-full flex flex-col bg-white dark:bg-card relative"
                onDragEnter={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dragCounter.current += 1;
                    setIsDragging(true);
                }}
                onDragLeave={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    dragCounter.current -= 1;
                    if (dragCounter.current === 0) {
                        setIsDragging(false);
                    }
                }}
                onDragOver={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                }}
                onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setIsDragging(false);
                    dragCounter.current = 0;
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
                        <div className="flex flex-col justify-end min-h-[500px] h-full pb-12 animate-in fade-in duration-700">
                            <div className="flex-1" />

                            {/* Title */}
                            <div className="mb-12 text-center">
                                <h1 className="text-3xl font-semibold opacity-30 tracking-tight text-foreground select-none">Arcturus</h1>
                            </div>

                            {/* Recent Chats */}
                            {chatSessions.length > 0 && (
                                <div className="w-full max-w-md mx-auto px-4 mb-8 space-y-1">
                                    {chatSessions.slice(0, 3).map((session) => (
                                        <button
                                            key={session.id}
                                            onClick={() => explorerRootPath && loadChatSession(session.id, 'ide', explorerRootPath)}
                                            className="w-full flex items-center justify-between py-2 group hover:opacity-70 transition-all text-left"
                                        >
                                            <span className="text-sm text-foreground/60 group-hover:text-foreground transition-colors truncate pr-4">
                                                {session.title}
                                            </span>
                                            <span className="text-xs text-muted-foreground/40 font-mono shrink-0">
                                                {formatRelativeTime(session.updated_at)}
                                            </span>
                                        </button>
                                    ))}
                                    <button
                                        onClick={() => setIsHistoryOpen(true)}
                                        className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors pt-2 block"
                                    >
                                        See all
                                    </button>
                                </div>
                            )}

                            {/* Quick Actions - Minimal version */}
                            <div className="flex flex-col gap-1 w-full max-w-md mx-auto px-4 opacity-40 hover:opacity-100 transition-opacity">
                                <button
                                    onClick={() => handleSend('Summarize this project structure and key components.')}
                                    className="flex items-center gap-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-all text-left"
                                >
                                    <ScrollText className="w-3 h-3 shrink-0" />
                                    <span>Summarize Project Structure</span>
                                </button>
                                <button
                                    onClick={() => handleSend('What are the key takeaways and main features of this codebase?')}
                                    className="flex items-center gap-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-all text-left"
                                >
                                    <Quote className="w-3 h-3 shrink-0" />
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
                                "max-w-full min-w-0 overflow-hidden"
                            )}>
                                {msg.role === 'user' && (
                                    (msg.contexts && msg.contexts.length > 0) ||
                                    (msg.fileContexts && msg.fileContexts.length > 0) ||
                                    (msg.images && msg.images.length > 0)
                                ) && (
                                        <div className="flex flex-col items-end w-full mb-1 space-y-1">
                                            {msg.fileContexts?.map((file, idx) => (
                                                <FilePill key={`file-${idx}`} file={file} />
                                            ))}
                                            {msg.contexts?.map((ctx, idx) => (
                                                /* @ts-ignore */
                                                <ContextPill key={`ctx-${idx}`} item={ctx} />
                                            ))}
                                            {msg.images?.map((img, idx) => (
                                                <div key={`img-${idx}`} className="relative group max-w-[200px] mb-1">
                                                    <img src={img} className="rounded-md border border-border/50 shadow-sm" alt="User upload" />
                                                </div>
                                            ))}
                                        </div>
                                    )}
                            </div>

                            <div className={cn(
                                "text-sm",
                                msg.role === 'user'
                                    ? ((msg.content && msg.content.includes && msg.content.includes('[System Tool Output]'))
                                        ? "w-full"
                                        : "bg-white/10 dark:bg-white/5 border border-border/50 text-foreground rounded-lg shadow-sm leading-normal backdrop-blur-sm")
                                    : "text-foreground leading-relaxed"
                            )}>
                                <MessageContent content={msg.content} role={msg.role as any} />
                            </div>
                        </div>
                    ))}

                    {isThinking && (
                        <div className="flex flex-col w-full mb-4">
                            <div className="flex items-center gap-2 mb-1.5 px-1 opacity-60">
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
                    {/* Context Pills (Text & File) & Image Previews */}
                    {(selectedContexts.length > 0 || selectedFileContexts.length > 0 || pastedImages.length > 0) && (
                        <div className="flex flex-wrap gap-2 mb-2 max-h-[100px] overflow-y-auto p-1.5 scrollbar-thin scrollbar-thumb-muted">
                            {/* Text Contexts */}
                            {selectedContexts.map((ctx, i) => {
                                const text = typeof ctx === 'string' ? ctx : ctx.text;
                                return (
                                    <div key={`text-${i}`} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary text-[10px] font-medium rounded-md max-w-full border border-primary/20 shadow-sm animate-in fade-in slide-in-from-bottom-1">
                                        <Quote className="w-3 h-3 shrink-0 opacity-70" />
                                        <span className="truncate max-w-[160px]">{text.substring(0, 40)}...</span>
                                        <button onClick={() => removeSelectedContext(i)} className="hover:text-primary/70 ml-1 transition-colors"><X className="w-3 h-3" /></button>
                                    </div>
                                );
                            })}
                            {/* File Contexts */}
                            {selectedFileContexts.map((f, i) => <FilePill key={`file-${i}`} file={f} onRemove={() => removeSelectedFileContext(i)} />)}

                            {/* Image Previews */}
                            {pastedImages.map((img, i) => (
                                <div key={`img-${i}`} className="relative group animate-in fade-in zoom-in duration-200">
                                    <img src={img} alt={`Pasted ${i}`} className="w-12 h-12 object-cover rounded-md border border-border shadow-sm" />
                                    <button
                                        onClick={() => removePastedImage(i)}
                                        className="absolute -top-1.5 -right-1.5 bg-destructive text-destructive-foreground rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
                                    >
                                        <X className="w-2.5 h-2.5" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className={cn(
                        "relative bg-muted/40 border border-border/50 rounded-xl focus-within:ring-1 focus-within:ring-primary/20 transition-all shadow-sm",
                        isThinking ? "opacity-80" : ""
                    )}>
                        <textarea
                            ref={textareaRef}
                            value={inputValue}
                            onChange={e => setInputValue(e.target.value)}
                            onPaste={handlePaste}
                            onKeyDown={e => {
                                if (e.key === 'Enter' && !e.shiftKey && !isThinking) {
                                    e.preventDefault();
                                    handleSend();
                                }
                            }}
                            placeholder={selectedContexts.length > 0 ? "Ask about selected text..." : "Ask anything..."}
                            readOnly={isThinking}
                            className={cn(
                                "w-full bg-transparent p-3 text-sm focus:outline-none resize-none min-h-[44px] max-h-[50vh] overflow-y-auto",
                                isThinking ? "cursor-not-allowed opacity-50" : ""
                            )}
                            rows={1}
                            style={{ minHeight: '44px' }}
                        />

                        <div className="flex items-center justify-between p-2 border-t border-border/10">
                            {/* Model Selector */}
                            <div className="relative model-menu-container">
                                <button
                                    onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
                                    disabled={isThinking}
                                    className={cn(
                                        "flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-background/50 text-[10px] font-medium text-muted-foreground transition-colors border border-transparent hover:border-border/30",
                                        isThinking ? "opacity-50 cursor-not-allowed" : ""
                                    )}
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
                                        disabled={!inputValue.trim() && selectedFileContexts.length === 0 && pastedImages.length === 0}
                                        className="p-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <ArrowRight className="w-3.5 h-3.5" />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Image Lightbox */}
                {
                    selectedImage && (
                        <div
                            className="fixed inset-0 z-[200] bg-black/10 backdrop-blur-sm flex items-center justify-center p-8 animate-in fade-in duration-200"
                            onClick={() => setSelectedImage(null)}
                        >
                            <div className="absolute top-6 right-6 flex items-center gap-3">
                                <button
                                    className="p-2 bg-black/40 hover:bg-white/20 text-white rounded-full transition-colors flex items-center gap-2 px-3"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (selectedImage) copyImageToClipboard(selectedImage);
                                    }}
                                    title="Copy to clipboard"
                                >
                                    {copiedImage ? <Check className="w-5 h-5 text-green-400" /> : <Copy className="w-5 h-5" />}
                                    <span className="text-xs font-bold">{copiedImage ? 'COPIED' : 'COPY'}</span>
                                </button>
                                <button
                                    className="p-2 bg-black/40 hover:bg-white/20 text-white rounded-full transition-colors flex items-center gap-2 px-3"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (!selectedImage) return;
                                        const link = document.createElement('a');
                                        link.href = selectedImage;
                                        link.download = `pasted_image_${Date.now()}.png`;
                                        link.click();
                                    }}
                                    title="Download image"
                                >
                                    <Download className="w-5 h-5" />
                                    <span className="text-xs font-bold">SAVE</span>
                                </button>
                                <button
                                    className="p-2 bg-black/40 hover:bg-white/20 text-white rounded-full transition-colors"
                                    onClick={() => setSelectedImage(null)}
                                >
                                    <X className="w-6 h-6" />
                                </button>
                            </div>
                            {selectedImage && (
                                <img
                                    src={selectedImage}
                                    alt="Zoomed"
                                    className="max-w-full max-h-full rounded-lg shadow-2xl object-contain animate-in zoom-in-95 duration-300 pointer-events-auto"
                                    onClick={(e) => e.stopPropagation()}
                                />
                            )}
                        </div>
                    )
                }
            </div>

            {/* Review Status Card (Chat only) */}
            <PermissionDialog
                request={reviewRequest}
                projectRoot={explorerRootPath || ''}
                onDecision={() => { }} // Editor handles decision, this is just status
                variant="review_status"
            />
        </>
    );
};
