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
import { api } from '@/lib/api';

// Import styles
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';

const API_BASE = 'http://localhost:8000';

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
        activeDocumentId,
        openDocuments,
        viewMode,
        addSelectedContext,
        setActiveDocument,
        closeDocument,
        closeAllDocuments
    } = useAppStore();

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
    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);
    const searchPluginInstance = searchPlugin();
    const { highlight, jumpToNextMatch } = searchPluginInstance;
    const defaultLayoutPluginInstance = defaultLayoutPlugin();
    const pageNavigationPluginInstance = pageNavigationPlugin();
    const { jumpToPage } = pageNavigationPluginInstance;

    // Store functions in refs to avoid dependency issues
    const highlightRef = useRef(highlight);
    const jumpToNextMatchRef = useRef(jumpToNextMatch);
    useEffect(() => {
        highlightRef.current = highlight;
        jumpToNextMatchRef.current = jumpToNextMatch;
    });

    // Auto-search for chunk text when PDF loads from SEEK result
    useEffect(() => {
        if (activeDoc?.searchText && pdfUrl) {
            // Delay to ensure PDF is fully loaded
            const timer = setTimeout(() => {
                // Clean the search text and trigger search
                const cleanText = activeDoc.searchText!.slice(0, 50).replace(/[*#\[\]()!\n]/g, ' ').trim();
                if (cleanText.length > 10) {
                    console.log('Auto-searching for:', cleanText);
                    highlightRef.current(cleanText);
                    // Jump to first match after a brief delay for search to complete
                    setTimeout(() => {
                        jumpToNextMatchRef.current();
                    }, 500);
                }
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [activeDoc?.searchText, pdfUrl]);

    const isImage = (type: string) => ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(type.toLowerCase());
    const canPreview = (type: string) => {
        const t = type.toLowerCase();
        return ['pdf', 'docx', 'doc', 'txt', 'md', 'json', 'ts', 'tsx', 'js', 'jsx', 'py', 'c', 'cpp', 'h', 'hpp', 'css', 'html'].includes(t);
    };
    const isCodeFile = (type: string) => ['py', 'js', 'ts', 'tsx', 'jsx', 'json', 'css', 'html', 'sh'].includes(type.toLowerCase());

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
                    style={document.documentElement.classList.contains('dark') ? vscDarkPlus : prism}
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
                    setIsCode(codeNode);
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
            <div className="flex items-center justify-between border-b border-border bg-muted/30 pr-4 shrink-0 h-12 shadow-md">
                <div className="flex items-center gap-[1px] px-2 h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {openDocuments.map(doc => (
                        <div
                            key={doc.id}
                            onClick={() => setActiveDocument(doc.id)}
                            className={cn(
                                "group flex items-center gap-0 px-2 h-10 mt-auto rounded-t-lg transition-all cursor-pointer min-w-[50px] max-w-[150px] border-x border-t border-transparent relative",
                                activeDocumentId === doc.id
                                    ? "bg-background border-border text-foreground z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-background"
                                    : "bg-muted/50 text-muted-foreground hover:bg-muted"
                            )}
                        >
                            {isCodeFile(doc.type) ? <Code2 className="w-3.5 h-3.5 shrink-0 text-blue-400" /> : <FileText className={cn("w-3.5 h-3.5 shrink-0", activeDocumentId === doc.id ? "text-primary" : "text-muted-foreground")} />}
                            <span className="text-[11px] font-medium truncate flex-1">{doc.title}</span>
                            <button
                                onClick={(e) => { e.stopPropagation(); closeDocument(doc.id); }}
                                className="p-1 rounded-md hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                    {openDocuments.length === 0 && (
                        <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/30">Discovery Workspace</div>
                    )}
                </div>

                <div className="flex items-center gap-3">
                    {openDocuments.length > 0 && (
                        <button
                            onClick={closeAllDocuments}
                            className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-white/5 text-[9px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-all bg-black/10 border border-border/50"
                        >
                            <X className="w-2.5 h-2.5" />
                            Clear
                        </button>
                    )}

                    {activeDoc && canPreview(activeDoc.type) && (
                        <>
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
                        </>
                    )}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative bg-background selection:bg-primary/20 select-text">
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
                    <div className="h-full overflow-hidden bg-[#2a2a2e]">
                        <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
                            <Viewer
                                fileUrl={pdfUrl}
                                plugins={[defaultLayoutPluginInstance, pageNavigationPluginInstance, searchPluginInstance]}
                                theme="dark"
                                onDocumentLoad={() => {
                                    // Trigger search if searchText is provided (from SEEK result)
                                    if (activeDoc?.searchText) {
                                        setTimeout(() => {
                                            const cleanText = activeDoc.searchText!.slice(0, 40).replace(/[*#\[\]()!\n]/g, ' ').trim();
                                            if (cleanText.length > 5) {
                                                console.log('Auto-searching for:', cleanText);
                                                highlight(cleanText);
                                                // Jump to first match after search completes
                                                setTimeout(() => jumpToNextMatchRef.current(), 500);
                                            }
                                        }, 300);
                                    }
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
                                                                "transition-all duration-300 overflow-hidden",
                                                                isExpanded ? "max-h-none opacity-100" : "max-h-[60px] opacity-80"
                                                            )}>
                                                                {isCodeFile(activeDoc.type) ? (
                                                                    <SyntaxHighlighter
                                                                        style={document.documentElement.classList.contains('dark') ? vscDarkPlus : prism}
                                                                        language={codeLang || 'text'}
                                                                        PreTag="div"
                                                                        customStyle={{
                                                                            margin: 0,
                                                                            padding: 0,
                                                                            background: 'transparent',
                                                                            fontSize: '11px',
                                                                            lineHeight: '1.6',
                                                                            // Force wrap for logic
                                                                            whiteSpace: "pre-wrap",
                                                                            wordBreak: "break-all"
                                                                        }}
                                                                        wrapLongLines={true}
                                                                    >
                                                                        {chunk}
                                                                    </SyntaxHighlighter>
                                                                ) : (
                                                                    <div className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-foreground/90 break-words">
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
                            <div className={cn("h-full overflow-hidden", (viewType === 'source' && isCode) ? "bg-[#1e1e1e]" : "bg-background")}>
                                {isCode && viewType === 'source' ? (
                                    <SyntaxHighlighter
                                        language={codeLang}
                                        style={vscDarkPlus}
                                        customStyle={{ margin: 0, height: '100%', fontSize: '14px', lineHeight: '1.5' }}
                                        showLineNumbers
                                    >
                                        {content}
                                    </SyntaxHighlighter>
                                ) : (
                                    <div className="h-full overflow-y-auto p-12 md:p-20 max-w-5xl mx-auto">
                                        <div className="prose prose-invert prose-lg max-w-none prose-headings:text-primary prose-strong:text-foreground prose-a:text-primary">
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
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground/30 space-y-8 bg-background">
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
