import React, { useEffect, useState, useRef } from 'react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { X, ExternalLink, Lock, ShieldCheck, Loader2, PlusCircle, FileText, Plus, Search } from 'lucide-react';
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
        openNewsTab,
        addSelectedContext
    } = useAppStore();

    const [htmlContent, setHtmlContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [urlInput, setUrlInput] = useState('');
    const iframeRef = useRef<HTMLIFrameElement>(null);

    const activeUrl = activeNewsTab || newsTabs[0];

    // Sync URL input with active tab
    useEffect(() => {
        if (activeUrl) {
            setUrlInput(activeUrl);
        }
    }, [activeUrl]);

    // Listen for navigation events from iframe
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            if (event.data?.type === 'NAVIGATE' && event.data.url) {
                // Navigate to the new URL by updating the current tab
                const newUrl = event.data.url;
                // Update the current tab's URL instead of opening a new tab
                const tabs = useAppStore.getState().newsTabs;
                const currentIdx = tabs.indexOf(activeUrl || '');
                if (currentIdx >= 0) {
                    // Replace current tab
                    const newTabs = [...tabs];
                    newTabs[currentIdx] = newUrl;
                    useAppStore.setState({ newsTabs: newTabs, activeNewsTab: newUrl });
                } else {
                    openNewsTab(newUrl);
                }
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [activeUrl, openNewsTab]);

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
                    // Inject a script to communicate text selection and link clicks back to parent
                    const injectedScript = `
                        <script>
                            // Text selection handling
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
                            
                            // Intercept all link clicks for navigation
                            document.addEventListener('click', function(e) {
                                const link = e.target.closest('a');
                                if (link && link.href) {
                                    const href = link.href;
                                    // Skip javascript: and # links
                                    if (href.startsWith('javascript:') || href === '#' || href.endsWith('#')) {
                                        return;
                                    }
                                    // Skip anchor links on same page
                                    if (href.includes('#') && href.split('#')[0] === window.location.href.split('#')[0]) {
                                        return;
                                    }
                                    e.preventDefault();
                                    e.stopPropagation();
                                    window.parent.postMessage({
                                        type: 'NAVIGATE',
                                        url: href
                                    }, '*');
                                }
                            }, true);
                            
                            // Intercept form submissions
                            document.addEventListener('submit', function(e) {
                                const form = e.target;
                                if (form && form.action) {
                                    e.preventDefault();
                                    const formData = new FormData(form);
                                    const params = new URLSearchParams(formData).toString();
                                    const url = form.method.toLowerCase() === 'get' 
                                        ? form.action + '?' + params 
                                        : form.action;
                                    window.parent.postMessage({
                                        type: 'NAVIGATE',
                                        url: url
                                    }, '*');
                                }
                            }, true);
                        </script>
                    `;
                    const modifiedHtml = res.data.html.replace('</body>', injectedScript + '</body>');
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

    // Handle URL navigation
    const handleNavigate = (input: string) => {
        if (!input.trim()) return;

        let url = input.trim();

        // If it's not a URL, search via DuckDuckGo
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            if (url.includes('.') && !url.includes(' ')) {
                // Looks like a domain
                url = 'https://' + url;
            } else {
                // Search query
                url = `https://duckduckgo.com/?q=${encodeURIComponent(url)}`;
            }
        }

        openNewsTab(url);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleNavigate(urlInput);
        }
    };

    // Handle new tab
    const handleNewTab = () => {
        // Open DuckDuckGo as default new tab
        openNewsTab('https://duckduckgo.com/');
    };

    // Show empty state if no tabs
    if (newsTabs.length === 0) {
        return (
            <div className="flex-1 flex flex-col bg-background overflow-hidden">
                {/* Empty Browser Toolbar */}
                <div className="h-10 bg-muted/40 flex items-center px-2 gap-1 border-b border-border/50 shrink-0">
                    <button
                        onClick={handleNewTab}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-cyan-400 hover:bg-cyan-500/10 rounded-md transition-colors"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        New Tab
                    </button>
                </div>

                {/* Empty State */}
                <div className="flex-1 flex flex-col items-center justify-center bg-background">
                    <div className="p-4 bg-muted rounded-full mb-4">
                        <Search className="w-8 h-8 text-muted-foreground/40" />
                    </div>
                    <h3 className="text-foreground font-bold mb-2">Start Browsing</h3>
                    <p className="text-sm text-muted-foreground mb-4">Select an article from the left panel or open a new tab</p>
                    <div className="flex items-center gap-2 w-full max-w-md">
                        <input
                            type="text"
                            value={urlInput}
                            onChange={(e) => setUrlInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Search or enter URL..."
                            className="flex-1 bg-muted/50 border border-border rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                        <button
                            onClick={() => handleNavigate(urlInput)}
                            className="px-4 py-2 bg-primary text-primary-foreground rounded-full text-sm font-medium hover:bg-primary/90"
                        >
                            Go
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col bg-background overflow-hidden">
            {/* Tab Bar */}
            <div className="h-10 bg-muted/40 flex items-center px-2 gap-1 overflow-x-auto scrollbar-hide border-b border-border/50 shrink-0">
                {newsTabs.map((url) => (
                    <div
                        key={url}
                        className={cn(
                            "group flex items-center gap-2 px-3 py-1.5 rounded-t-lg text-[11px] font-medium transition-all max-w-[180px] shrink-0 cursor-pointer",
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

                {/* New Tab Button */}
                <button
                    onClick={handleNewTab}
                    className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground hover:text-foreground shrink-0"
                    title="New Tab"
                >
                    <Plus className="w-4 h-4" />
                </button>

                <div className="flex-1" />

                <button
                    onClick={closeAllNewsTabs}
                    className="text-[10px] text-muted-foreground hover:text-red-400 px-2 font-bold uppercase tracking-tighter transition-colors"
                >
                    Close All
                </button>
            </div>

            {/* Browser-like Toolbar with Editable URL */}
            <div className="h-10 bg-card border-b border-border/50 flex items-center px-4 gap-3 shrink-0">
                <div className="flex-1 flex items-center gap-2 bg-muted/50 px-3 py-1 rounded-full border border-border/50 focus-within:ring-2 focus-within:ring-primary/50">
                    <Lock className="w-3 h-3 text-green-500/60 shrink-0" />
                    <input
                        type="text"
                        value={urlInput}
                        onChange={(e) => setUrlInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Enter URL or search..."
                        className="flex-1 bg-transparent text-[11px] text-foreground font-mono focus:outline-none"
                    />
                </div>

                <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono shrink-0">
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
                        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
                        title="Article Content"
                    />
                )}

                {/* Selection Menu - floats above iframe */}
                <SelectionMenu onAdd={(text) => addSelectedContext(text)} />
            </div>
        </div>
    );
};
