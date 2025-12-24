import React, { useEffect, useState, useRef } from 'react';
import { X, FileText, Loader2, Library, Code2, Quote, PlusCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { renderAsync } from 'docx-preview';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
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
            active ? (label === 'Insights' ? "bg-primary text-charcoal-950" : "bg-white/10 text-white") : "text-muted-foreground hover:text-white"
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
            className="fixed z-[9999] flex items-center gap-2 p-1 bg-charcoal-800 border border-border rounded-lg shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-200"
            style={{ left: position.x, top: position.y, transform: 'translateX(-50%)' }}
        >
            <button
                onMouseDown={handleAddClick}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition-all active:scale-95",
                    isAdded
                        ? "bg-green-500 text-white shadow-lg shadow-green-500/20"
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
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [docxBlob, setDocxBlob] = useState<Blob | null>(null);
    const [viewType, setViewType] = useState<'source' | 'ai'>('source');
    const [isDocx, setIsDocx] = useState(false);
    const [isCode, setIsCode] = useState(false);
    const [codeLang, setCodeLang] = useState('javascript');

    const docxContainerRef = useRef<HTMLDivElement>(null);
    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);
    const defaultLayoutPluginInstance = defaultLayoutPlugin();

    const isImage = (type: string) => ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(type.toLowerCase());
    const canPreview = (type: string) => ['pdf', 'docx', 'doc'].includes(type.toLowerCase());
    const isCodeFile = (type: string) => ['py', 'js', 'ts', 'tsx', 'jsx', 'json', 'css', 'html', 'sh'].includes(type.toLowerCase());

    useEffect(() => {
        if (!activeDoc) {
            setContent(null);
            setPdfUrl(null);
            setImageUrl(null);
            setDocxBlob(null);
            setIsDocx(false);
            setIsCode(false);
            return;
        }

        const loadContent = async () => {
            setLoading(true);
            try {
                const docType = activeDoc.type.toLowerCase();
                const codeNode = isCodeFile(docType);

                if (docType === 'py') setCodeLang('python');
                else if (docType === 'js') setCodeLang('javascript');
                else if (docType === 'ts' || docType === 'tsx') setCodeLang('typescript');
                else setCodeLang(docType);

                // For AI View or forced DOCX AI
                if (viewType === 'ai' && canPreview(docType)) {
                    const res = await axios.get(`${API_BASE}/rag/document_preview`, {
                        params: { path: activeDoc.id }
                    });
                    let markdown = res.data.markdown || "No preview available.";
                    markdown = markdown.replace(/!\[\]\(images\//g, `![](${API_BASE}/rag/images/`);
                    setContent(markdown);
                    setPdfUrl(null);
                    setImageUrl(null);
                    setDocxBlob(null);
                    setIsDocx(false);
                    setIsCode(false); // AI View is always Markdown
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
            <div className="flex items-center justify-between border-b border-border bg-charcoal-900 pr-4 shrink-0 h-12 shadow-md">
                <div className="flex items-center gap-[1px] px-2 h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {openDocuments.map(doc => (
                        <div
                            key={doc.id}
                            onClick={() => setActiveDocument(doc.id)}
                            className={cn(
                                "group flex items-center gap-2 px-4 h-9 mt-auto rounded-t-lg transition-all cursor-pointer min-w-[140px] max-w-[200px] border-x border-t border-transparent relative",
                                activeDocumentId === doc.id
                                    ? "bg-charcoal-950 border-border text-white z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-charcoal-950"
                                    : "bg-charcoal-900/30 text-muted-foreground hover:bg-white/5"
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
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md hover:bg-white/5 text-[9px] font-bold uppercase tracking-wider text-muted-foreground hover:text-white transition-all bg-black/20 border border-white/5"
                        >
                            <X className="w-2.5 h-2.5" />
                            Clear
                        </button>
                    )}

                    {activeDoc && canPreview(activeDoc.type) && (
                        <div className="flex items-center bg-black/40 rounded-lg p-0.5 border border-white/5">
                            <TabButton
                                label="Source"
                                active={viewType === 'source'}
                                onClick={() => setViewType('source')}
                            />
                            <TabButton
                                label="Insights"
                                active={viewType === 'ai'}
                                onClick={() => setViewType('ai')}
                            />
                        </div>
                    )}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative bg-charcoal-950 selection:bg-primary/20 select-text">
                {loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-charcoal-950 z-[100] space-y-4">
                        <div className="p-4 rounded-2xl bg-charcoal-900 border border-white/5 shadow-2xl">
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
                                plugins={[defaultLayoutPluginInstance]}
                                theme="dark"
                            />
                        </Worker>
                    </div>
                )}

                {/* Image Viewer */}
                {isImage(activeDoc?.type || '') && imageUrl && (
                    <div className="h-full flex items-center justify-center p-8 bg-charcoal-950 overflow-auto">
                        <img
                            src={imageUrl}
                            alt={activeDoc?.title}
                            className="max-w-full max-h-full object-contain rounded-lg shadow-2xl border border-white/10 shadow-black/80"
                        />
                    </div>
                )}

                {/* DOCX Viewer (Source Mode) */}
                {isDocx && viewType === 'source' && (
                    <div className="h-full overflow-y-auto bg-charcoal-900 p-8 docx-viewer">
                        <div ref={docxContainerRef} className="max-w-[900px] mx-auto min-h-full" />
                    </div>
                )}

                {/* Markdown / Code Viewer */}
                {content !== null && !isDocx && (
                    <>
                        {/* Insights View (Markdown Extraction) */}
                        {viewType === 'ai' && activeDoc && canPreview(activeDoc.type) ? (
                            <div className="flex-1 overflow-y-auto p-12 bg-charcoal-900 select-text relative group">
                                <div className="max-w-[800px] mx-auto prose prose-invert">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            img: ({ node, ...props }) => (
                                                <img {...props} className="rounded-lg border border-white/10 shadow-xl max-w-full my-8" />
                                            ),
                                            table: ({ node, ...props }) => (
                                                <div className="overflow-x-auto my-6 border border-white/10 rounded-lg">
                                                    <table {...props} className="min-w-full border-collapse" />
                                                </div>
                                            ),
                                            th: ({ node, ...props }) => <th {...props} className="bg-white/5 p-3 text-left font-bold border-b border-white/10" />,
                                            td: ({ node, ...props }) => <td {...props} className="p-3 border-b border-white/5" />
                                        }}
                                    >
                                        {content || "Extracting insights..."}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        ) : (
                            <div className="h-full overflow-y-auto p-12 md:p-20 max-w-5xl mx-auto">
                                {isCode && viewType === 'source' ? (
                                    <div className="rounded-xl overflow-hidden border border-white/5 bg-black/40 shadow-2xl">
                                        <SyntaxHighlighter
                                            language={codeLang}
                                            style={vscDarkPlus}
                                            customStyle={{ margin: 0, padding: '2rem', fontSize: '13px', background: 'transparent' }}
                                            showLineNumbers
                                        >
                                            {content}
                                        </SyntaxHighlighter>
                                    </div>
                                ) : (
                                    <div className="prose prose-invert prose-lg max-w-none prose-headings:text-primary prose-strong:text-white prose-a:text-primary">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
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
                {!activeDoc && (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground/30 space-y-8 bg-charcoal-950">
                        <div className="relative">
                            <div className="absolute inset-0 bg-primary/20 blur-[80px] rounded-full" />
                            <div className="relative p-10 rounded-[3rem] bg-charcoal-900 border border-white/5 shadow-inner">
                                <Library className="w-24 h-24 opacity-20" />
                            </div>
                        </div>
                        <div className="text-center space-y-3 z-10">
                            <h3 className="text-sm font-bold uppercase tracking-[0.5em] text-primary/40">Discovery Workspace</h3>
                            <p className="text-[11px] italic opacity-40 max-w-xs leading-relaxed">Select a document from the left panel to begin your deep research flow.</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
