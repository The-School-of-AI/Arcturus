import React, { useEffect, useState, useRef } from 'react';
import { X, FileText, Loader2, Library, Code2, Quote, PlusCircle, Sparkles, MessageSquare, ListChecks, Send } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { pageNavigationPlugin } from '@react-pdf-viewer/page-navigation';
import { searchPlugin } from '@react-pdf-viewer/search';
import '@react-pdf-viewer/page-navigation/lib/styles/index.css';
import '@react-pdf-viewer/search/lib/styles/index.css';
import { renderAsync } from 'docx-preview';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, prism } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { api, API_BASE } from '@/lib/api';
import { useTheme } from '@/components/theme';

// Import styles
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';

interface TabButtonProps {
    label: string;
    active: boolean;
    onClick: () => void;
}

const TabButton: React.FC<TabButtonProps> = ({ label, active, onClick }) => (
    <button
        onClick={onClick}
        className={cn(
            "px-3 py-1 rounded-md text-[9px] font-bold uppercase tracking-tighter transition-all",
            active ? "bg-white text-black shadow-sm" : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
        )}
    >
        {label}
    </button>
);

interface SelectionMenuProps {
    onAdd: (text: string) => void;
}

const SelectionMenu: React.FC<SelectionMenuProps> = ({ onAdd }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [currentText, setCurrentText] = useState("");
    const [isAdded, setIsAdded] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleSelectionChange = () => {
            const selection = window.getSelection();
            const text = selection?.toString().trim();

            if (text && text.length > 0) {
                try {
                    const range = selection!.getRangeAt(0);
                    const rect = range.getBoundingClientRect();
                    setPosition({
                        x: rect.left + rect.width / 2,
                        y: rect.top - 40,
                    });
                    setCurrentText(text);
                    setIsVisible(true);
                } catch (e) {
                    setIsVisible(false);
                }
            } else if (!isAdded) {
                setIsVisible(false);
            }
        };

        document.addEventListener('selectionchange', handleSelectionChange);
        return () => {
            document.removeEventListener('selectionchange', handleSelectionChange);
        };
    }, [isAdded]);

    const handleAddClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        e.preventDefault();
        if (currentText) {
            onAdd(currentText);
            setIsAdded(true);
            setTimeout(() => {
                setIsVisible(false);
                setIsAdded(false);
            }, 600);
        }
    };

    if (!isVisible) return null;

    return (
        <div
            ref={menuRef}
            className="fixed z-[9999] flex items-center gap-2 p-1 bg-popover border border-border rounded-lg shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-200"
            style={{ left: position.x, top: position.y, transform: 'translateX(-50%)' }}
        >
            <button
                onMouseDown={handleAddClick}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition-all active:scale-95",
                    isAdded
                        ? "bg-green-500 text-foreground shadow-lg shadow-green-500/20"
                        : "bg-primary text-primary-foreground hover:shadow-lg hover:shadow-primary/20"
                )}
            >
                {isAdded ? (
                    <><PlusCircle className="w-3.5 h-3.5" /> Added!</>
                ) : (
                    <><PlusCircle className="w-3.5 h-3.5" /> Add to Context</>
                )}
            </button>
        </div>
    );
};

export const DocumentViewer: React.FC = () => {
    const {
        ragActiveDocumentId,
        ragOpenDocuments,
        viewMode,
        addSelectedContext,
        setActiveRagDocument,
        closeRagDocument,
        closeAllRagDocuments,
        showRagInsights,
        toggleRagInsights
    } = useAppStore();
    const { theme } = useTheme();

    const [content, setContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [chunks, setChunks] = useState<string[] | null>(null);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [docxBlob, setDocxBlob] = useState<Blob | null>(null);
    const [viewType, setViewType] = useState<'source' | 'ai'>('source');
    const [isDocx, setIsDocx] = useState(false);
    const [isCode, setIsCode] = useState(false);
    const [codeLang, setCodeLang] = useState('javascript');
    const [expandedChunk, setExpandedChunk] = useState<number | null>(null);

    // Insights Panel State
    const [showInsights, setShowInsights] = useState(false);
    const [insightsLoading, setInsightsLoading] = useState(false);
    const [insightsResult, setInsightsResult] = useState<string | null>(null);
    const [insightsQuestion, setInsightsQuestion] = useState('');

    const docxContainerRef = useRef<HTMLDivElement>(null);
    const activeDoc = ragOpenDocuments.find(d => d.id === ragActiveDocumentId);
    // ✅ CORRECT: Call the plugin hooks at the top level
    const searchPluginInstance = searchPlugin();
    const { highlight, jumpToNextMatch } = searchPluginInstance;

    const defaultLayoutPluginInstance = defaultLayoutPlugin();

    const pageNavigationPluginInstance = pageNavigationPlugin();
    const { jumpToPage } = pageNavigationPluginInstance;

    // Store functions in refs to avoid dependency issues
    const highlightRef = useRef(highlight);
    const jumpToNextMatchRef = useRef(jumpToNextMatch);

    // Track previous document to determine jump speed
    const prevDocIdRef = useRef<string | null>(null);

    useEffect(() => {
        highlightRef.current = highlight;
        jumpToNextMatchRef.current = jumpToNextMatch;
    });

    // Track what we've already navigated to (prevents infinite loops)
    const lastNavigatedRef = useRef<{ docId: string; page: number | null; text: string | null } | null>(null);

    // Auto-search for chunk text when PDF loads from SEEK result
    useEffect(() => {
        if (pdfUrl && activeDoc) {
            // Check if we already navigated to this exact target
            const current = lastNavigatedRef.current;
            if (current &&
                current.docId === activeDoc.id &&
                current.page === (activeDoc.targetPage || null) &&
                current.text === (activeDoc.searchText || null)) {
                // Already navigated, skip
                return;
            }

            // Determine if we are switching docs or just nav within same doc
            const isSameDoc = prevDocIdRef.current === activeDoc.id;
            prevDocIdRef.current = activeDoc.id;

            // Fast jump for same doc, slow jump for new doc (waiting for worker)
            const delay = isSameDoc ? 100 : 1200;

            const timer = setTimeout(() => {
                // Mark as navigated BEFORE executing to prevent re-runs
                lastNavigatedRef.current = {
                    docId: activeDoc.id,
                    page: activeDoc.targetPage || null,
                    text: activeDoc.searchText || null
                };

                // 1. Jump to page if specified (guaranteed page number)
                if (activeDoc.targetPage && activeDoc.targetPage > 0) {
                    console.log(`Jumping to page (delay ${delay}ms):`, activeDoc.targetPage);
                    jumpToPage(activeDoc.targetPage - 1); // 0-indexed
                }

                // 2. Search and Highlight if text provided
                if (activeDoc.searchText) {
                    // Clean the search text: remove markdown symbols, captions, and newlines
                    const cleaned = activeDoc.searchText
                        .replace(/\*\*\[Image Caption\]:\*\*/gi, '') // Remove caption label
                        .replace(/[#*\[\]()!]/g, ' ')               // Remove MD symbols
                        .replace(/\s+/g, ' ')                        // Collapse spaces
                        .trim();

                    const searchStr = cleaned.slice(0, 45);

                    if (searchStr.length > 5) {
                        try {
                            // Escape regex characters to safely create a pattern
                            const escapedStr = searchStr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                            console.log('Auto-searching for (Regex):', searchStr);

                            // Use case-insensitive regex for robust matching
                            highlightRef.current(new RegExp(escapedStr, 'gi'));

                            // Jump to first match after a brief delay for search to complete
                            setTimeout(() => {
                                jumpToNextMatchRef.current();
                            }, 500);
                        } catch (e) {
                            console.error("Auto-highlight failed", e);
                        }
                    }
                }
                // 3. Jump to Line if provided (Ripgrep)
                if (activeDoc.targetLine && activeDoc.targetLine > 0) {
                    const lineElement = document.getElementById(`line-${activeDoc.targetLine}`);
                    if (lineElement) {
                        console.log("Scrolling to line:", activeDoc.targetLine);
                        lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
            }, delay);

            return () => clearTimeout(timer);
        }
    }, [activeDoc?.id, activeDoc?.targetPage, activeDoc?.targetLine, activeDoc?.searchText, pdfUrl, jumpToPage]);

    const isImage = (type: string) => ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(type.toLowerCase());
    const canPreview = (type: string) => {
        const t = type.toLowerCase();
        return ['pdf', 'docx', 'doc', 'txt', 'md', 'json', 'ts', 'tsx', 'js', 'jsx', 'py', 'c', 'cpp', 'h', 'hpp', 'css', 'html', 'png', 'jpg', 'jpeg', 'gif', 'webp'].includes(t);
    };
    const isCodeFile = (type: string) => ['py', 'js', 'ts', 'tsx', 'jsx', 'json', 'css', 'html', 'sh', 'txt', 'md'].includes(type.toLowerCase());

    const markdownComponents = {
        img: ({ node, ...props }: any) => (
            <img {...props} className="rounded-lg border border-border shadow-xl max-w-full my-8" />
        ),
        table: ({ node, ...props }: any) => (
            <div className="overflow-x-auto my-6 border border-border rounded-lg">
                <table {...props} className="min-w-full border-collapse" />
            </div>
        ),
        th: ({ node, ...props }: any) => <th {...props} className="bg-muted p-3 text-left font-bold border-b border-border" />,
        td: ({ node, ...props }: any) => <td {...props} className="p-3 border-b border-border/50" />,
        code({ node, className, children, ref, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            return match ? (
                <SyntaxHighlighter
                    {...props}
                    children={String(children).replace(/\n$/, '')}
                    style={theme === 'dark' ? vscDarkPlus : prism}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{ margin: '1em 0', borderRadius: '0.5rem', background: 'transparent' }}
                />
            ) : (
                <code {...props} className={cn("bg-muted px-1.5 py-0.5 rounded font-mono text-sm", className)}>
                    {children}
                </code>
            );
        }
    };

    useEffect(() => {
        if (!activeDoc) {
            setContent(null);
            setChunks(null);
            setPdfUrl(null);
            setImageUrl(null);
            setDocxBlob(null);
            setIsDocx(false);
            setIsCode(false);
            setExpandedChunk(null);
            return;
        }

        const loadContent = async () => {
            setLoading(true);
            setChunks(null);
            setExpandedChunk(null);
            try {
                const docType = activeDoc.type.toLowerCase();
                const codeNode = isCodeFile(docType);

                if (docType === 'py') setCodeLang('python');
                else if (docType === 'js') setCodeLang('javascript');
                else if (docType === 'ts' || docType === 'tsx') setCodeLang('typescript');
                else setCodeLang(docType);

                // For AI View - use cached chunks for FAST loading
                if (viewType === 'ai' && canPreview(docType)) {
                    // Try fast chunks first
                    const res = await axios.get(`${API_BASE}/rag/document_chunks`, {
                        params: { path: activeDoc.id }
                    });
                    if (res.data.status === 'success') {
                        const chunkData = res.data.chunks;
                        if (chunkData && Array.isArray(chunkData)) {
                            setChunks(chunkData);
                        }
                        // Keep content as fallback equivalent if chunks fail, or construction string
                        const markdown = res.data.markdown || "No chunks available.";
                        setContent(`*${res.data.chunk_count} chunks indexed*\n\n---\n\n${markdown}`);
                    } else {
                        // Fallback message
                        setContent("Document not indexed yet. Please index first.");
                        setChunks(null);
                    }
                    setPdfUrl(null);
                    setImageUrl(null);
                    setDocxBlob(null);
                    setIsDocx(false);
                    setIsCode(false);
                } else if (docType === 'pdf') {
                    const response = await fetch(`${API_BASE}/rag/document_content?path=${encodeURIComponent(activeDoc.id)}`);
                    if (!response.ok) throw new Error("Fetch failed");
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    setPdfUrl(url);
                    setContent(null);
                    setImageUrl(null);
                    setDocxBlob(null);
                    setIsDocx(false);
                    setIsCode(false);
                } else if (isImage(docType)) {
                    const response = await fetch(`${API_BASE}/rag/document_content?path=${encodeURIComponent(activeDoc.id)}`);
                    if (!response.ok) throw new Error("Fetch failed");
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    setImageUrl(url);
                    setPdfUrl(null);
                    setContent(null);
                    setDocxBlob(null);
                    setIsDocx(false);
                    setIsCode(false);
                } else if (docType === 'docx' || docType === 'doc') {
                    const response = await fetch(`${API_BASE}/rag/document_content?path=${encodeURIComponent(activeDoc.id)}`);
                    if (!response.ok) throw new Error("Fetch failed");
                    const blob = await response.blob();
                    setDocxBlob(blob);
                    setIsDocx(true);
                    setIsCode(false);
                    setContent(null);
                    setPdfUrl(null);
                    setImageUrl(null);
                } else {
                    const res = await axios.get(`${API_BASE}/rag/document_content`, {
                        params: { path: activeDoc.id }
                    });
                    const data = res.data;
                    setContent(typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2));
                    setPdfUrl(null);
                    setImageUrl(null);
                    setDocxBlob(null);
                    setIsDocx(false);
                    setIsCode(codeNode || !!activeDoc.targetLine);
                }
            } catch (e) {
                console.error("Failed to load document content", e);
                setContent("### ❌ Error Loading Content\nThis document might be binary or corrupted. Use **AI View** for complex documents.");
            } finally {
                setLoading(false);
            }
        };

        loadContent();

        return () => {
            if (pdfUrl) URL.revokeObjectURL(pdfUrl);
            if (imageUrl) URL.revokeObjectURL(imageUrl);
        };
    }, [activeDoc?.id, viewType]);

    // Secondary effect for DOCX rendering - triggered by blob or ref readiness
    useEffect(() => {
        if (docxBlob && isDocx && viewType === 'source' && docxContainerRef.current) {
            docxContainerRef.current.innerHTML = "";
            renderAsync(docxBlob, docxContainerRef.current).catch(err => {
                console.error("docx-preview error:", err);
            });
        }
    }, [docxBlob, isDocx, viewType, !!docxContainerRef.current]);

    // Visibility is managed by parent (AppLayout)

    return (
        <div className="h-full flex flex-col relative">
            {/* Tab Bar - Browser Style */}
            <div className="flex items-center justify-between border-b border-border bg-muted/30 pr-4 shrink-0 h-12">
                <div className="flex items-center gap-[1px] px-2 h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {ragOpenDocuments.map(doc => (
                        <div
                            key={doc.id}
                            onClick={() => setActiveRagDocument(doc.id)}
                            className={cn(
                                "group flex items-center gap-0 px-2 h-10 mt-auto rounded-t-lg transition-all cursor-pointer min-w-[50px] max-w-[150px] border-x border-t border-transparent relative",
                                ragActiveDocumentId === doc.id
                                    ? "bg-background border-border text-foreground z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-background"
                                    : "bg-muted/50 text-muted-foreground hover:bg-muted"
                            )}
                        >
                            {isCodeFile(doc.type) ? <Code2 className="w-3.5 h-3.5 shrink-0 text-blue-400" /> : <FileText className={cn("w-3.5 h-3.5 shrink-0", ragActiveDocumentId === doc.id ? "text-primary" : "text-muted-foreground")} />}
                            <span className="text-[11px] font-medium truncate flex-1">{doc.title}</span>
                            <button
                                onClick={(e) => { e.stopPropagation(); closeRagDocument(doc.id); }}
                                className="p-1 rounded-md hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                    {ragOpenDocuments.length === 0 && (
                        <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/90">Discovery Workspace</div>
                    )}
                </div>

                <div className="flex items-center gap-3">
                    {ragOpenDocuments.length > 0 && (
                        <button
                            onClick={closeAllRagDocuments}
                            className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-white/5 text-[9px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-all bg-black/10 border border-border/50"
                        >
                            <X className="w-2.5 h-2.5" />
                            Clear
                        </button>
                    )}

                    {activeDoc && canPreview(activeDoc.type) && (
                        <div className="flex items-center gap-2">
                            <div className="flex items-center bg-black/10 rounded-lg p-0.5 border border-border/50">
                                <TabButton
                                    label="Source"
                                    active={viewType === 'source'}
                                    onClick={() => setViewType('source')}
                                />
                                <TabButton
                                    label="Chunks"
                                    active={viewType === 'ai'}
                                    onClick={() => setViewType('ai')}
                                />
                            </div>

                            <button
                                onClick={toggleRagInsights}
                                className={cn(
                                    "flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all text-[9px] font-bold uppercase tracking-wider border",
                                    showRagInsights
                                        ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(59,130,246,0.3)]"
                                        : "bg-black/10 text-muted-foreground hover:text-foreground border-border/50 hover:bg-black/20"
                                )}
                                title="Toggle Insights Panel"
                            >
                                <Sparkles className={cn("w-3.5 h-3.5", showRagInsights ? "animate-pulse" : "opacity-70")} />
                                Insights
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative bg-transparent selection:bg-primary/20 select-text">
                {loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-background z-[100] space-y-4">
                        <div className="p-4 rounded-2xl bg-card border border-border/50 shadow-2xl">
                            <Loader2 className="w-10 h-10 text-primary animate-spin" />
                        </div>
                        <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-primary/60 animate-pulse">Initializing Extraction...</div>
                    </div>
                )}

                {/* PDF Viewer */}
                {activeDoc?.type.toLowerCase() === 'pdf' && pdfUrl && viewType === 'source' && (
                    <div className={cn("h-full overflow-hidden", theme === 'dark' ? "bg-[#2a2a2e]" : "bg-[#ebebeb]")}>
                        <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
                            <Viewer
                                fileUrl={pdfUrl}
                                plugins={[defaultLayoutPluginInstance, pageNavigationPluginInstance, searchPluginInstance]}
                                theme={theme}
                                onDocumentLoad={() => {
                                    // Initial load logic if needed
                                }}
                            />
                        </Worker>
                    </div>
                )}

                {/* Image Viewer */}
                {isImage(activeDoc?.type || '') && imageUrl && (
                    <div className="h-full flex items-center justify-center p-8 bg-background overflow-auto">
                        <img
                            src={imageUrl}
                            alt={activeDoc?.title}
                            className="max-w-full max-h-full object-contain rounded-lg shadow-2xl border border-border shadow-black/80"
                        />
                    </div>
                )}

                {/* DOCX Viewer (Source Mode) */}
                {isDocx && viewType === 'source' && (
                    <div className="h-full overflow-y-auto bg-background p-8 docx-viewer">
                        <div ref={docxContainerRef} className="max-w-[900px] mx-auto min-h-full" />
                    </div>
                )}

                {content !== null && !isDocx && (
                    <>
                        {/* Insights View (Markdown Extraction) */}
                        {viewType === 'ai' && activeDoc && canPreview(activeDoc.type) ? (
                            <div className="absolute inset-0 overflow-y-auto p-12 bg-background select-text">
                                <div className="max-w-[800px] mx-auto">
                                    {chunks ? (
                                        <div className="space-y-4">
                                            {chunks.map((chunk, i) => {
                                                const isExpanded = expandedChunk === i;
                                                return (
                                                    <div
                                                        key={i}
                                                        onClick={() => setExpandedChunk(isExpanded ? null : i)}
                                                        className={cn(
                                                            "rounded-xl border bg-card shadow-sm overflow-hidden transition-all duration-300 cursor-pointer group hover:border-primary/40",
                                                            isExpanded ? "border-primary/40 ring-1 ring-primary/20 shadow-md" : "border-border hover:shadow-sm"
                                                        )}
                                                    >
                                                        <div className={cn(
                                                            "px-4 py-2 border-b flex items-center justify-between transition-colors",
                                                            isExpanded ? "bg-primary/5 border-primary/20" : "bg-muted/30 border-border/50 group-hover:bg-muted/50"
                                                        )}>
                                                            <div className="flex items-center gap-2">
                                                                <div className={cn("w-1.5 h-1.5 rounded-full transition-colors", isExpanded ? "bg-primary" : "bg-muted-foreground/40")} />
                                                                <span className={cn("text-[10px] font-bold uppercase tracking-widest", isExpanded ? "text-primary" : "text-muted-foreground")}>
                                                                    Chunk {i + 1}
                                                                </span>
                                                            </div>
                                                            {isCodeFile(activeDoc.type) && <span className="text-[10px] font-mono text-primary/70">{activeDoc.type.toUpperCase()}</span>}
                                                        </div>

                                                        <div className="relative p-4">
                                                            <div className={cn(
                                                                "transition-all duration-300",
                                                                isExpanded
                                                                    ? "opacity-100 h-auto max-h-none"
                                                                    : "max-h-[48px] opacity-80 overflow-x-auto no-scrollbar whitespace-nowrap"
                                                            )}>
                                                                {isCodeFile(activeDoc.type) ? (
                                                                    <SyntaxHighlighter
                                                                        style={theme === 'dark' ? vscDarkPlus : prism}
                                                                        language={codeLang || 'text'}
                                                                        PreTag="div"
                                                                        customStyle={{
                                                                            margin: 0,
                                                                            padding: 0,
                                                                            background: 'transparent',
                                                                            fontSize: '11px',
                                                                            lineHeight: '1.6',
                                                                        }}
                                                                        codeTagProps={{
                                                                            style: {
                                                                                whiteSpace: isExpanded ? 'pre-wrap' : 'pre',
                                                                                wordBreak: isExpanded ? 'break-word' : 'normal',
                                                                                fontFamily: 'inherit'
                                                                            }
                                                                        }}
                                                                        wrapLongLines={isExpanded}
                                                                    >
                                                                        {chunk}
                                                                    </SyntaxHighlighter>
                                                                ) : (
                                                                    <div className={cn(
                                                                        "font-mono text-[11px] leading-relaxed text-foreground/90 transition-all",
                                                                        isExpanded ? "whitespace-pre-wrap break-words" : "whitespace-nowrap"
                                                                    )}>
                                                                        {chunk}
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {/* Gradient mask for unexpanded state */}
                                                            {!isExpanded && (
                                                                <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-card to-transparent pointer-events-none" />
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="prose dark:prose-invert">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm]}
                                                components={markdownComponents}
                                            >
                                                {content}
                                            </ReactMarkdown>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ) : (
                            /* Code View */
                            <div className={cn("h-full overflow-hidden", (viewType === 'source' && isCode) ? (theme === 'dark' ? "bg-transparent/50" : "bg-transparent") : "bg-transparent")}>
                                {isCode && viewType === 'source' ? (
                                    <SyntaxHighlighter
                                        language={codeLang}
                                        style={theme === 'dark' ? vscDarkPlus : prism}
                                        customStyle={{ margin: 0, height: '100%', fontSize: '14px', lineHeight: '1.5', background: 'transparent' }}
                                        showLineNumbers
                                        wrapLines={true}
                                        wrapLongLines={true}
                                        codeTagProps={{
                                            style: {
                                                whiteSpace: 'pre-wrap',
                                                wordBreak: 'break-word'
                                            }
                                        }}
                                        lineProps={(lineNumber) => {
                                            const style: React.CSSProperties = { display: 'block', width: '100%' };
                                            if (lineNumber === activeDoc?.targetLine) {
                                                style.backgroundColor = 'rgba(255, 255, 0, 0.2)';
                                                style.borderLeft = '3px solid #eab308';
                                            }
                                            return {
                                                style,
                                                id: `line-${lineNumber}`
                                            };
                                        }}
                                    >
                                        {content}
                                    </SyntaxHighlighter>
                                ) : (
                                    <div className="h-full overflow-y-auto p-12 md:p-20 max-w-5xl mx-auto">
                                        <div className={cn("prose prose-lg max-w-none prose-headings:text-primary prose-strong:text-foreground prose-a:text-primary", theme === 'dark' && "prose-invert")}>
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* Floating Selection Tool - Visible for all document types when active */}
                {activeDoc && (
                    <SelectionMenu onAdd={(text) => addSelectedContext(text)} />
                )}

                {/* Empty State */}
                {!activeDoc ? (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground/30 space-y-8 bg-transparent">
                        <div className="relative">
                            <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full" />
                            <div className="relative p-10 rounded-[3rem] bg-card border border-border/50 shadow-inner">
                                <FileText className="w-24 h-24 text-primary/40" />
                            </div>
                        </div>
                        <div className="text-center space-y-2">
                            <h3 className="text-xl font-bold text-foreground tracking-tight">Document Viewer</h3>
                            <p className="text-sm">Select a document from the library to view</p>
                        </div>
                    </div>
                ) : null}
            </div>
        </div >
    );
};
