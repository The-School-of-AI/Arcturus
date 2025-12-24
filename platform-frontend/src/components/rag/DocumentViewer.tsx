import React, { useEffect, useState } from 'react';
import { X, FileText, Loader2, Library } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';

// Import styles
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';

const API_BASE = 'http://localhost:8000';

export const DocumentViewer: React.FC = () => {
    const {
        openDocuments,
        activeDocumentId,
        closeDocument,
        setActiveDocument,
        viewMode
    } = useAppStore();

    const [content, setContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [viewType, setViewType] = useState<'source' | 'ai'>('source');

    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);
    const defaultLayoutPluginInstance = defaultLayoutPlugin();

    const isMedia = (type: string) => ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp'].includes(type.toLowerCase());
    const isImage = (type: string) => ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(type.toLowerCase());
    const canPreview = (type: string) => ['pdf', 'docx', 'doc'].includes(type.toLowerCase());

    useEffect(() => {
        if (!activeDoc) return;

        const loadContent = async () => {
            setLoading(true);
            try {
                const docType = activeDoc.type.toLowerCase();

                // For DOCX/DOC/Binary, we almost always want 'ai' view because source is binary
                if ((viewType === 'ai' && canPreview(docType)) || docType === 'docx' || docType === 'doc') {
                    const res = await axios.get(`${API_BASE}/rag/document_preview`, {
                        params: { path: activeDoc.id }
                    });

                    // Fix MuPDF image paths: ![](images/foo.png) -> ![](http://localhost:8000/rag/images/foo.png)
                    let markdown = res.data.markdown || "No preview available.";
                    markdown = markdown.replace(/!\[\]\(images\//g, `![](${API_BASE}/rag/images/`);

                    setContent(markdown);
                    setPdfUrl(null);
                    setImageUrl(null);
                } else if (docType === 'pdf') {
                    // Use native fetch to be 100% sure about binary integrity (no axios interceptors)
                    const response = await fetch(`${API_BASE}/rag/document_content?path=${encodeURIComponent(activeDoc.id)}`);
                    if (!response.ok) throw new Error("Failed to fetch PDF");
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);

                    setPdfUrl(url);
                    setContent(null);
                    setImageUrl(null);
                } else if (isImage(docType)) {
                    const response = await fetch(`${API_BASE}/rag/document_content?path=${encodeURIComponent(activeDoc.id)}`);
                    if (!response.ok) throw new Error("Failed to fetch image");
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);

                    setImageUrl(url);
                    setPdfUrl(null);
                    setContent(null);
                } else {
                    const res = await axios.get(`${API_BASE}/rag/document_content`, {
                        params: { path: activeDoc.id }
                    });
                    const data = res.data;
                    setContent(typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2));
                    setPdfUrl(null);
                    setImageUrl(null);
                }
            } catch (e) {
                console.error("Failed to load document content", e);
                setContent("### ❌ Error Loading Content\nThis document might be binary or corrupted. Use **AI View** for complex documents like PDFs or Word files.");
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

    if (viewMode !== 'rag') return null;

    return (
        <div className="flex flex-col h-full bg-charcoal-950">
            {/* Tab Bar and Toggles */}
            <div className="flex items-center justify-between border-b border-border bg-charcoal-900/50 pr-4 shrink-0">
                <div className="flex items-center gap-1 px-4 pt-3 overflow-x-auto no-scrollbar">
                    {openDocuments.map(doc => (
                        <div
                            key={doc.id}
                            onClick={() => setActiveDocument(doc.id)}
                            className={cn(
                                "group flex items-center gap-2 px-4 py-2 rounded-t-lg border-x border-t transition-all cursor-pointer min-w-[140px] max-w-[240px]",
                                activeDocumentId === doc.id
                                    ? "bg-charcoal-950 border-border text-white shadow-[0_-2px_15px_rgba(0,0,0,0.5)]"
                                    : "bg-charcoal-900/30 border-transparent text-muted-foreground hover:bg-white/5"
                            )}
                        >
                            <FileText className={cn("w-3.5 h-3.5 shrink-0", activeDocumentId === doc.id ? "text-primary" : "text-muted-foreground")} />
                            <span className="text-[11px] font-bold uppercase tracking-tight truncate flex-1">{doc.title}</span>
                            <button
                                onClick={(e) => { e.stopPropagation(); closeDocument(doc.id); }}
                                className="p-1 rounded-md hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                    {openDocuments.length === 0 && (
                        <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground opacity-50">Viewer Ready</div>
                    )}
                </div>

                {activeDoc && canPreview(activeDoc.type) && (
                    <div className="flex items-center bg-black/40 rounded-full p-0.5 border border-white/5 mt-2">
                        <button
                            onClick={() => setViewType('source')}
                            className={cn(
                                "px-3 py-1 rounded-full text-[9px] font-bold uppercase tracking-tighter transition-all",
                                viewType === 'source' ? "bg-primary text-charcoal-950" : "text-muted-foreground hover:text-white"
                            )}
                        >
                            Original
                        </button>
                        <button
                            onClick={() => setViewType('ai')}
                            className={cn(
                                "px-3 py-1 rounded-full text-[9px] font-bold uppercase tracking-tighter transition-all",
                                viewType === 'ai' ? "bg-primary text-charcoal-950" : "text-muted-foreground hover:text-white"
                            )}
                        >
                            AI View
                        </button>
                    </div>
                )}
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative selection:bg-primary/20">
                {loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-charcoal-950/80 backdrop-blur-sm z-50 space-y-4">
                        <div className="p-4 rounded-xl bg-charcoal-900 border border-white/5 shadow-2xl">
                            <Loader2 className="w-8 h-8 text-primary animate-spin" />
                        </div>
                        <div className="text-[10px] font-bold uppercase tracking-widest text-primary/80">Indexing Context...</div>
                    </div>
                )}

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

                {isImage(activeDoc?.type || '') && imageUrl && (
                    <div className="h-full flex items-center justify-center p-8 bg-charcoal-950 overflow-auto">
                        <img
                            src={imageUrl}
                            alt={activeDoc?.title}
                            className="max-w-full max-h-full object-contain rounded-lg shadow-2xl border border-white/5"
                        />
                    </div>
                )}

                {(content !== null) && (
                    <div className="h-full overflow-y-auto p-12 max-w-4xl mx-auto">
                        <div className="prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown>{content}</ReactMarkdown>
                        </div>
                    </div>
                )}

                {!activeDoc && (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground/30 space-y-6">
                        <div className="p-6 rounded-3xl bg-white/5 border border-white/5 shadow-inner">
                            <Library className="w-20 h-20 opacity-10" />
                        </div>
                        <div className="text-center space-y-2">
                            <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-muted-foreground">Empty Workspace</p>
                            <p className="text-xs italic opacity-50">Select a document to begin deep analysis</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
