import React, { useEffect, useState, useRef } from 'react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { X, ExternalLink, Lock, ShieldCheck, Loader2, PlusCircle, FileText, Plus, Search } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import 'github-markdown-css/github-markdown.css';

// Selection Menu Component for adding text to context
interface SelectionMenuProps {
    onAdd: (text: string) => void;
    onShowChat: () => void;
    activeUrl: string | null;
    iframeRef: React.RefObject<HTMLIFrameElement | null>;
}

const SelectionMenu: React.FC<SelectionMenuProps> = ({ onAdd, onShowChat, activeUrl, iframeRef }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [currentText, setCurrentText] = useState("");
    const [isAdded, setIsAdded] = useState(false);

    // Clear visibility when active URL changes (switching tabs)
    useEffect(() => {
        setIsVisible(false);
        setCurrentText("");
    }, [activeUrl]);

    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            // Listen for selection events from iframe
            if (event.data?.type === 'TEXT_SELECTED') {
                const { text, x, y, source } = event.data;
                if (text && text.length > 0) {
                    let finalX = x;
                    let finalY = y;

                    // If simple coordinates from iframe (clientX/Y), add iframe offset
                    if (source === 'iframe' && iframeRef.current) {
                        const iframeRect = iframeRef.current.getBoundingClientRect();
                        finalX += iframeRect.left;
                        finalY += iframeRect.top;
                    }

                    setPosition({ x: finalX, y: finalY - 30 });
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
            onShowChat(); // Show the chat panel when adding context
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
        addSelectedContext,
        setShowNewsChatPanel
    } = useAppStore();

    const [htmlContent, setHtmlContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [urlInput, setUrlInput] = useState('');
    const [readerMode, setReaderMode] = useState(false);
    const [readerContent, setReaderContent] = useState<string | null>(null);
    const [loadingReader, setLoadingReader] = useState(false);
    const [isGithubReadme, setIsGithubReadme] = useState(false);
    const [zoomLevel, setZoomLevel] = useState(100);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const iframeRef = useRef<HTMLIFrameElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

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

    // Content cache with 30-minute TTL
    // Content cache with 30-minute TTL
    const contentCacheRef = useRef<Map<string, {
        html: string;
        timestamp: number;
        readerMode?: boolean;
        readerContent?: string | null;
        isGithubReadme?: boolean;
    }>>(new Map());
    const CACHE_TTL = 30 * 60 * 1000; // 30 minutes

    // Fetch rendered HTML when tab changes (with caching)
    useEffect(() => {
        if (!activeUrl) {
            setHtmlContent(null);
            return;
        }

        // Check cache first
        const cached = contentCacheRef.current.get(activeUrl);
        const now = Date.now();
        if (cached && (now - cached.timestamp) < CACHE_TTL) {
            setHtmlContent(cached.html);
            // Restore extended state if available
            if (cached.readerMode !== undefined) setReaderMode(cached.readerMode);
            else setReaderMode(false);

            if (cached.readerContent !== undefined) setReaderContent(cached.readerContent);
            else setReaderContent(null);

            if (cached.isGithubReadme !== undefined) setIsGithubReadme(cached.isGithubReadme);
            else setIsGithubReadme(false);

            setError(null);
            return;
        }

        // Reset state if not in cache
        setReaderMode(false);
        setReaderContent(null);
        setIsGithubReadme(false);

        const fetchContent = async () => {
            setLoading(true);
            setError(null);

            // Special handling for GitHub URLs - try to fetch README
            const githubMatch = activeUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
            if (githubMatch) {
                const [, owner, repo] = githubMatch;
                const cleanRepo = repo.replace(/\?.*$/, '').replace(/#.*$/, ''); // Remove query/hash
                try {
                    // Try to fetch README.md from raw.githubusercontent.com
                    const readmeUrls = [
                        `https://raw.githubusercontent.com/${owner}/${cleanRepo}/main/README.md`,
                        `https://raw.githubusercontent.com/${owner}/${cleanRepo}/master/README.md`,
                    ];

                    for (const readmeUrl of readmeUrls) {
                        try {
                            const readmeRes = await axios.get(readmeUrl, { timeout: 5000 });
                            if (readmeRes.status === 200 && typeof readmeRes.data === 'string') {
                                // Got README, auto-activate reader mode with this content
                                setReaderContent(readmeRes.data);
                                setReaderMode(true);
                                setIsGithubReadme(true);
                                setLoading(false);
                                // Cache the content with extended state
                                contentCacheRef.current.set(activeUrl, {
                                    html: '<div>GitHub README - Using Reader Mode</div>',
                                    timestamp: Date.now(),
                                    readerMode: true,
                                    readerContent: readmeRes.data,
                                    isGithubReadme: true
                                });
                                return;
                            }
                        } catch (e) {
                            // README not found at this path, try next
                        }
                    }
                } catch (e) {
                    // Fall through to regular fetch
                }
            }

            try {
                const res = await axios.get(`${API_BASE}/news/article`, {
                    params: { url: activeUrl }
                });
                if (res.data.status === 'success') {
                    // Inject a script to communicate text selection and link clicks back to parent
                    const injectedScript = `
                        <script>
                            // Text selection handling
                            document.addEventListener('mouseup', function(e) {
                                const selection = window.getSelection();
                                const text = selection ? selection.toString().trim() : '';
                                if (text && text.length > 0) {
                                    // Use mouse coordinates for better positioning
                                    const x = e.clientX;
                                    const y = e.clientY;
                                    
                                    window.parent.postMessage({
                                        type: 'TEXT_SELECTED',
                                        text: text,
                                        x: x,
                                        y: y,
                                        source: 'iframe'
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
                            
                            // Auto-dismiss cookie banners
                            setTimeout(function() {
                                // Common cookie consent button selectors
                                const cookieSelectors = [
                                    // Accept buttons
                                    'button[id*="accept"]',
                                    'button[id*="Accept"]',
                                    'button[class*="accept"]',
                                    'button[class*="Accept"]',
                                    'button[aria-label*="Accept"]',
                                    'button[aria-label*="accept"]',
                                    'button[data-testid*="accept"]',
                                    // Reject buttons
                                    'button[id*="reject"]',
                                    'button[class*="reject"]',
                                    'button[aria-label*="Reject"]',
                                    // Close buttons on modals
                                    '[class*="cookie"] button',
                                    '[id*="cookie"] button',
                                    '[class*="consent"] button',
                                    '[id*="consent"] button',
                                    '[class*="gdpr"] button',
                                    // Specific sites
                                    '.cc-dismiss',
                                    '.cc-btn-accept',
                                    '#onetrust-accept-btn-handler',
                                    '.accept-cookies',
                                    '.cookie-accept',
                                    '#cookie-accept',
                                    '.js-accept-cookies'
                                ];
                                
                                for (const selector of cookieSelectors) {
                                    const buttons = document.querySelectorAll(selector);
                                    buttons.forEach(function(btn) {
                                        const text = btn.textContent?.toLowerCase() || '';
                                        if (text.includes('accept') || text.includes('agree') || text.includes('ok') || text.includes('got it') || text.includes('reject') || text.includes('close')) {
                                            btn.click();
                                        }
                                    });
                                }
                                
                                // Also try to hide common cookie banner containers
                                const bannerSelectors = [
                                    '[class*="cookie-banner"]',
                                    '[class*="cookie-notice"]',
                                    '[class*="cookie-consent"]',
                                    '[id*="cookie-banner"]',
                                    '[id*="cookie-notice"]',
                                    '[class*="cookieBanner"]',
                                    '[class*="gdpr"]',
                                    '.cc-window',
                                    '#onetrust-banner-sdk'
                                ];
                                
                                bannerSelectors.forEach(function(sel) {
                                    const els = document.querySelectorAll(sel);
                                    els.forEach(function(el) {
                                        el.style.display = 'none';
                                    });
                                });
                            }, 1000);
                        </script>
                    `;
                    const modifiedHtml = res.data.html.replace('</body>', injectedScript + '</body>');
                    setHtmlContent(modifiedHtml);
                    // Cache the content
                    contentCacheRef.current.set(activeUrl, { html: modifiedHtml, timestamp: Date.now() });
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
                    <p className="text-sm text-muted-foreground">Select an article from the left panel or use the sidebar search.</p>
                </div>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="flex-1 flex flex-col bg-background overflow-hidden">
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

                <div className="flex items-center gap-2 shrink-0">
                    {/* Reader Mode Toggle - hidden for GitHub READMEs */}
                    {!isGithubReadme && (
                        <button
                            onClick={async () => {
                                if (!readerMode && activeUrl) {
                                    setLoadingReader(true);
                                    try {
                                        const res = await axios.get(`${API_BASE}/news/reader`, {
                                            params: { url: activeUrl }
                                        });
                                        if (res.data.status === 'success') {
                                            setReaderContent(res.data.content);
                                            setReaderMode(true);
                                        }
                                    } catch (e) {
                                        console.error('Failed to fetch reader content', e);
                                    }
                                    setLoadingReader(false);
                                } else {
                                    setReaderMode(false);
                                }
                            }}
                            className={cn(
                                "px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-md transition-colors",
                                readerMode
                                    ? "bg-cyan-500 text-white"
                                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                            )}
                            disabled={loadingReader}
                        >
                            {loadingReader ? 'Loading...' : 'Reader'}
                        </button>
                    )}
                    <button
                        onClick={() => window.open(activeUrl, '_blank')}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground"
                        title="Open in browser"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </button>

                    <div className="w-px h-4 bg-border/50 mx-1" />

                    {/* Zoom Controls */}
                    <div className="flex items-center bg-muted/50 rounded-md border border-border/50">
                        <button
                            onClick={() => setZoomLevel(Math.max(50, zoomLevel - 10))}
                            className="p-1 hover:bg-background rounded-l-md transition-colors text-muted-foreground"
                            title="Zoom Out"
                        >
                            <span className="text-[10px] font-bold px-1">-</span>
                        </button>
                        <span className="text-[10px] px-1 min-w-[3ch] text-center font-mono">{zoomLevel}%</span>
                        <button
                            onClick={() => setZoomLevel(Math.min(200, zoomLevel + 10))}
                            className="p-1 hover:bg-background rounded-r-md transition-colors text-muted-foreground"
                            title="Zoom In"
                        >
                            <Plus className="w-3 h-3" />
                        </button>
                    </div>

                    {/* Fullscreen Toggle */}
                    <button
                        onClick={() => {
                            if (!document.fullscreenElement) {
                                containerRef.current?.requestFullscreen();
                                setIsFullscreen(true);
                            } else {
                                document.exitFullscreen();
                                setIsFullscreen(false);
                            }
                        }}
                        className={cn(
                            "p-1.5 rounded-md transition-colors",
                            isFullscreen
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-muted text-muted-foreground"
                        )}
                        title="Toggle Fullscreen"
                    >
                        {isFullscreen ? (
                            <X className="w-3.5 h-3.5" /> // Using X for exit fullscreen
                        ) : (
                            <div className="w-3.5 h-3.5 border-2 border-current rounded-[1px]" /> // Simple box icon
                        )}
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

                {/* Reader Mode - Markdown Content */}
                {readerMode && readerContent && !loading && (
                    <div
                        className="w-full h-full overflow-y-auto bg-background p-8"
                        onMouseUp={(e) => {
                            const selection = window.getSelection();
                            const text = selection ? selection.toString().trim() : '';
                            if (text && text.length > 0) {
                                const range = selection!.getRangeAt(0);
                                const rect = range.getBoundingClientRect();
                                // Simulate the same message as iframe
                                window.postMessage({
                                    type: 'TEXT_SELECTED',
                                    text: text,
                                    x: rect.left + rect.width / 2,
                                    y: rect.top,
                                    source: 'reader'
                                }, '*');
                            }
                        }}
                        onMouseDown={() => {
                            window.postMessage({ type: 'SELECTION_CLEARED' }, '*');
                        }}
                    >
                        {/* Use GitHub markdown styling for GitHub READMEs */}
                        {/* Use GitHub markdown styling for GitHub READMEs */}
                        <div className={cn(
                            "max-w-3xl mx-auto",
                            isGithubReadme
                                ? "markdown-body"
                                : "prose prose-slate dark:prose-invert prose-sm"
                        )} style={{
                            ...(isGithubReadme ? { backgroundColor: 'white', padding: '2rem', borderRadius: '0.5rem' } : undefined),
                            transform: `scale(${zoomLevel / 100})`,
                            transformOrigin: 'top center'
                        }}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {readerContent}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}

                {/* Web Mode - Iframe */}
                {!readerMode && htmlContent && !loading && (
                    <iframe
                        ref={iframeRef}
                        srcDoc={htmlContent}
                        className="w-full h-full border-0"
                        style={{ zoom: zoomLevel / 100 }}
                        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
                        title="Article Content"
                    />
                )}

                {/* Selection Menu - floats above iframe */}
                <SelectionMenu
                    onAdd={(text) => addSelectedContext(text)}
                    onShowChat={() => setShowNewsChatPanel(true)}
                    activeUrl={activeUrl ?? null}
                    iframeRef={iframeRef}
                />
            </div>
        </div>
    );
};
