import React, { useEffect, useState, useRef } from 'react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { X, ExternalLink, Lock, ShieldCheck, Loader2, PlusCircle, FileText } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

// Selection Menu Component for adding text to context
interface SelectionMenuProps {
    onAdd: (text: string) => void;
}

const SelectionMenu: React.FC<SelectionMenuProps> = ({ onAdd }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [currentText, setCurrentText] = useState("");
    const [isAdded, setIsAdded] = useState(false);

    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            // Listen for selection events from iframe
            if (event.data?.type === 'TEXT_SELECTED') {
                const { text, x, y } = event.data;
                if (text && text.length > 0) {
                    setPosition({ x, y: y - 40 });
                    setCurrentText(text);
                    setIsVisible(true);
                }
            } else if (event.data?.type === 'SELECTION_CLEARED') {
                if (!isAdded) {
                    setIsVisible(false);
                }
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
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

export const NewsArticleViewer: React.FC = () => {
    const {
        newsTabs,
        activeNewsTab,
        setActiveNewsTab,
        closeNewsTab,
        closeAllNewsTabs,
        addSelectedContext
    } = useAppStore();

    const [htmlContent, setHtmlContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const iframeRef = useRef<HTMLIFrameElement>(null);

    const activeUrl = activeNewsTab || newsTabs[0];

    // Fetch rendered HTML when tab changes
    useEffect(() => {
        if (!activeUrl) {
            setHtmlContent(null);
            return;
        }

        const fetchContent = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await axios.get(`${API_BASE}/news/article`, {
                    params: { url: activeUrl }
                });
                if (res.data.status === 'success') {
                    // Inject a script to communicate text selection back to parent
                    const selectionScript = `
                        <script>
                            document.addEventListener('mouseup', function() {
                                const selection = window.getSelection();
                                const text = selection ? selection.toString().trim() : '';
                                if (text && text.length > 0) {
                                    const range = selection.getRangeAt(0);
                                    const rect = range.getBoundingClientRect();
                                    window.parent.postMessage({
                                        type: 'TEXT_SELECTED',
                                        text: text,
                                        x: rect.left + rect.width / 2,
                                        y: rect.top + window.scrollY
                                    }, '*');
                                }
                            });
                            document.addEventListener('mousedown', function() {
                                window.parent.postMessage({ type: 'SELECTION_CLEARED' }, '*');
                            });
                        </script>
                    `;
                    const modifiedHtml = res.data.html.replace('</body>', selectionScript + '</body>');
                    setHtmlContent(modifiedHtml);
                } else {
                    setError(res.data.error || 'Failed to load page');
                }
            } catch (e: any) {
                console.error("Failed to fetch article:", e);
                setError(e.message || 'Network error');
            } finally {
                setLoading(false);
            }
        };

        fetchContent();
    }, [activeUrl]);

    if (newsTabs.length === 0) return null;

    return (
        <div className="flex-1 flex flex-col bg-background overflow-hidden">
            {/* Tab Bar */}
            <div className="h-10 bg-muted/40 flex items-center px-2 gap-1 overflow-x-auto scrollbar-hide border-b border-border/50 shrink-0">
                {newsTabs.map((url) => (
                    <div
                        key={url}
                        className={cn(
                            "group flex items-center gap-2 px-3 py-1.5 rounded-t-lg text-[11px] font-medium transition-all max-w-[200px] shrink-0 cursor-pointer",
                            activeNewsTab === url
                                ? "bg-card text-foreground shadow-sm border-t border-x border-border/50"
                                : "text-muted-foreground hover:bg-muted/60"
                        )}
                        onClick={() => setActiveNewsTab(url)}
                    >
                        <FileText className="w-3 h-3 text-cyan-400 shrink-0" />
                        <span className="truncate flex-1">{new URL(url).hostname}</span>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                closeNewsTab(url);
                            }}
                            className="p-0.5 hover:bg-muted rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                ))}

                <div className="flex-1" />

                <button
                    onClick={closeAllNewsTabs}
                    className="text-[10px] text-muted-foreground hover:text-red-400 px-2 font-bold uppercase tracking-tighter transition-colors"
                >
                    Close All
                </button>
            </div>

            {/* Browser-like Toolbar */}
            <div className="h-10 bg-card border-b border-border/50 flex items-center px-4 gap-3 shrink-0">
                <div className="flex-1 flex items-center gap-2 bg-muted/50 px-3 py-1 rounded-full border border-border/50">
                    <Lock className="w-3 h-3 text-green-500/60" />
                    <span className="text-[11px] text-muted-foreground truncate font-mono">{activeUrl}</span>
                </div>

                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                    <ShieldCheck className="w-3.5 h-3.5 text-cyan-500/60" />
                    <span className="uppercase tracking-widest hidden sm:block">Rendered</span>
                    <button
                        onClick={() => window.open(activeUrl, '_blank')}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors"
                        title="Open in browser"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* Content Area - Iframe with rendered HTML */}
            <div className="flex-1 overflow-hidden bg-white relative">
                {loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-background z-10 space-y-4">
                        <div className="p-4 rounded-2xl bg-card border border-border/50 shadow-2xl">
                            <Loader2 className="w-10 h-10 text-primary animate-spin" />
                        </div>
                        <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-primary/60 animate-pulse">Rendering Page...</div>
                    </div>
                )}

                {error && !loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background">
                        <div className="max-w-md text-center space-y-4 p-8">
                            <div className="p-4 bg-red-500/10 rounded-full w-fit mx-auto">
                                <X className="w-8 h-8 text-red-400" />
                            </div>
                            <h3 className="text-foreground font-bold">Failed to Load Page</h3>
                            <p className="text-sm text-muted-foreground">{error}</p>
                            <button
                                onClick={() => window.open(activeUrl, '_blank')}
                                className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium"
                            >
                                <ExternalLink className="w-4 h-4" />
                                Open in Browser
                            </button>
                        </div>
                    </div>
                )}

                {htmlContent && !loading && (
                    <iframe
                        ref={iframeRef}
                        srcDoc={htmlContent}
                        className="w-full h-full border-0"
                        sandbox="allow-scripts allow-same-origin"
                        title="Article Content"
                    />
                )}

                {/* Selection Menu - floats above iframe */}
                <SelectionMenu onAdd={(text) => addSelectedContext(text)} />
            </div>
        </div>
    );
};
