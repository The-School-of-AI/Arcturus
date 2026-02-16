import React, { useEffect, useState, useRef, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
    ChevronLeft, ChevronRight, RotateCw, Plus, X, Lock, Globe,
    ExternalLink, Loader2, Search, PlusCircle, Minus
} from 'lucide-react';
import { useAppStore } from '@/store';

interface BrowserTabInfo {
    tabId: string;
    url: string;
    title: string;
    loading: boolean;
    canGoBack: boolean;
    canGoForward: boolean;
}

export const ElectronBrowserView: React.FC = () => {
    const {
        newsTabs,
        activeNewsTab,
        setActiveNewsTab,
        closeNewsTab,
        closeAllNewsTabs,
        openNewsTab,
        addSelectedContext,
        setShowNewsChatPanel,
        sidebarTab
    } = useAppStore();

    // Map store URLs to WebContentsView tab IDs
    const [urlToTabId, setUrlToTabId] = useState<Map<string, string>>(new Map());
    const [tabInfo, setTabInfo] = useState<Map<string, BrowserTabInfo>>(new Map());
    const [isLoading, setIsLoading] = useState(false);
    const [canGoBack, setCanGoBack] = useState(false);
    const [canGoForward, setCanGoForward] = useState(false);
    const [urlInput, setUrlInput] = useState('');
    const [zoomLevel, setZoomLevel] = useState(100);

    const containerRef = useRef<HTMLDivElement>(null);
    const resizeObserverRef = useRef<ResizeObserver | null>(null);
    const creatingTabsRef = useRef<Set<string>>(new Set());

    // Update bounds when container size/position changes
    const updateBounds = useCallback(() => {
        if (!containerRef.current || !window.electronAPI) return;

        const rect = containerRef.current.getBoundingClientRect();

        // Electron's setBounds uses logical pixels (DIPs), same as getBoundingClientRect.
        // We do NOT need to multiply by devicePixelRatio.
        const bounds = {
            x: Math.round(rect.left),
            y: Math.round(rect.top),
            width: Math.round(rect.width),
            height: Math.round(rect.height)
        };

        window.electronAPI.send('browser:set-bounds', bounds);
    }, []);

    // Hide browser on unmount
    useEffect(() => {
        return () => {
            if (window.electronAPI) {
                window.electronAPI.send('browser:hide-all', {});
            }
        };
    }, []);

    // Setup resize observer
    useEffect(() => {
        if (!containerRef.current) return;

        resizeObserverRef.current = new ResizeObserver(() => {
            updateBounds();
        });

        resizeObserverRef.current.observe(containerRef.current);
        window.addEventListener('resize', updateBounds);

        // Initial bounds update with delay to ensure layout is complete
        const timer = setTimeout(() => {
            updateBounds();
        }, 100);

        return () => {
            clearTimeout(timer);
            resizeObserverRef.current?.disconnect();
            window.removeEventListener('resize', updateBounds);
        };
    }, [updateBounds]);

    // Hide browser views when leaving News tab, show when returning
    useEffect(() => {
        if (!window.electronAPI) return;

        if (sidebarTab === 'news') {
            window.electronAPI.send('browser:show-active', {});
            // Update bounds after showing
            setTimeout(updateBounds, 50);
        } else {
            window.electronAPI.send('browser:hide-all', {});
        }
    }, [sidebarTab, updateBounds]);

    // Subscribe to browser events from main process
    useEffect(() => {
        if (!window.electronAPI) return;

        const handleNavigate = (data: { tabId: string; url: string; canGoBack: boolean; canGoForward: boolean }) => {
            setTabInfo(prev => {
                const updated = new Map(prev);
                const existing = updated.get(data.tabId);
                if (existing) {
                    updated.set(data.tabId, { ...existing, url: data.url, canGoBack: data.canGoBack, canGoForward: data.canGoForward });
                }
                return updated;
            });

            // Update URL input if this is the active tab
            const activeTabId = urlToTabId.get(activeNewsTab || '');
            if (data.tabId === activeTabId) {
                setUrlInput(data.url);
                setCanGoBack(data.canGoBack);
                setCanGoForward(data.canGoForward);
            }
        };

        const handleTitleUpdate = (data: { tabId: string; title: string }) => {
            setTabInfo(prev => {
                const updated = new Map(prev);
                const existing = updated.get(data.tabId);
                if (existing) {
                    updated.set(data.tabId, { ...existing, title: data.title });
                }
                return updated;
            });
        };

        const handleLoadingChange = (data: { tabId: string; loading: boolean }) => {
            setTabInfo(prev => {
                const updated = new Map(prev);
                const existing = updated.get(data.tabId);
                if (existing) {
                    updated.set(data.tabId, { ...existing, loading: data.loading });
                }
                return updated;
            });

            const activeTabId = urlToTabId.get(activeNewsTab || '');
            if (data.tabId === activeTabId) {
                setIsLoading(data.loading);
            }
        };

        window.electronAPI.receive('browser:did-navigate', handleNavigate);
        window.electronAPI.receive('browser:title-updated', handleTitleUpdate);
        window.electronAPI.receive('browser:loading-changed', handleLoadingChange);

        return () => { };
    }, [activeNewsTab, urlToTabId]);

    // Create WebContentsView for new store tabs
    useEffect(() => {
        if (!window.electronAPI) return;

        const createMissingTabs = async () => {
            for (const url of newsTabs) {
                if (!urlToTabId.has(url) && !creatingTabsRef.current.has(url)) {
                    creatingTabsRef.current.add(url);
                    try {
                        const result = await window.electronAPI?.invoke('browser:create-tab', url);
                        if (result?.tabId) {
                            setUrlToTabId(prev => new Map(prev).set(url, result.tabId));
                            setTabInfo(prev => new Map(prev).set(result.tabId, {
                                tabId: result.tabId,
                                url: result.url,
                                title: result.title || 'New Tab',
                                loading: true,
                                canGoBack: false,
                                canGoForward: false
                            }));
                        }
                    } finally {
                        creatingTabsRef.current.delete(url);
                    }
                }
            }
        };

        createMissingTabs();
    }, [newsTabs, urlToTabId]);

    // Switch active tab in main process when store's activeNewsTab changes
    useEffect(() => {
        if (!window.electronAPI || !activeNewsTab) return;

        const tabId = urlToTabId.get(activeNewsTab);
        if (tabId) {
            window.electronAPI.invoke('browser:switch-tab', tabId).then(result => {
                if (result?.success) {
                    setUrlInput(result.url || activeNewsTab);
                    setCanGoBack(result.canGoBack || false);
                    setCanGoForward(result.canGoForward || false);
                    updateBounds();
                }
            });
        }
    }, [activeNewsTab, urlToTabId, updateBounds]);

    // Close WebContentsView for removed store tabs
    useEffect(() => {
        if (!window.electronAPI) return;

        urlToTabId.forEach((tabId, url) => {
            if (!newsTabs.includes(url)) {
                window.electronAPI?.invoke('browser:close-tab', tabId);
                setUrlToTabId(prev => {
                    const updated = new Map(prev);
                    updated.delete(url);
                    return updated;
                });
                setTabInfo(prev => {
                    const updated = new Map(prev);
                    updated.delete(tabId);
                    return updated;
                });
            }
        });
    }, [newsTabs, urlToTabId]);

    // Update URL input when active tab changes
    useEffect(() => {
        if (activeNewsTab) {
            setUrlInput(activeNewsTab);
        }
    }, [activeNewsTab]);

    // Get active tab info
    const activeTabId = activeNewsTab ? urlToTabId.get(activeNewsTab) : null;
    const activeTabInfo = activeTabId ? tabInfo.get(activeTabId) : null;

    // Apply zoom when zoom level changes
    useEffect(() => {
        if (!window.electronAPI || !activeTabId) return;
        const zoomFactor = zoomLevel / 100;
        window.electronAPI.invoke('browser:set-zoom', { tabId: activeTabId, zoomFactor });
    }, [zoomLevel, activeTabId]);

    // Navigation handlers
    const navigate = async (targetUrl: string) => {
        if (!window.electronAPI || !activeTabId) return;

        let url = targetUrl.trim();
        if (!url) return;

        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            if (url.includes('.') && !url.includes(' ')) {
                url = 'https://' + url;
            } else {
                url = `https://duckduckgo.com/?q=${encodeURIComponent(url)}`;
            }
        }

        await window.electronAPI.invoke('browser:navigate', { tabId: activeTabId, url });
    };

    const goBack = async () => {
        if (!window.electronAPI || !activeTabId) return;
        await window.electronAPI.invoke('browser:go-back', activeTabId);
    };

    const goForward = async () => {
        if (!window.electronAPI || !activeTabId) return;
        await window.electronAPI.invoke('browser:go-forward', activeTabId);
    };

    const reload = async () => {
        if (!window.electronAPI || !activeTabId) return;
        await window.electronAPI.invoke('browser:reload', activeTabId);
    };

    const addSelectionToContext = async () => {
        if (!window.electronAPI || !activeTabId) return;

        const result = await window.electronAPI.invoke('browser:get-selection', activeTabId);
        if (result?.success && result.text) {
            addSelectedContext(result.text);
            setShowNewsChatPanel(true);
        }
    };

    const handleNewTab = () => {
        openNewsTab('https://duckduckgo.com/');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            navigate(urlInput);
        }
    };

    // Get title for a store URL
    const getTitleForUrl = (url: string): string => {
        const tabId = urlToTabId.get(url);
        if (tabId) {
            const info = tabInfo.get(tabId);
            if (info?.title && info.title !== 'New Tab') return info.title;
        }
        try {
            return new URL(url).hostname;
        } catch {
            return 'New Tab';
        }
    };

    const getLoadingForUrl = (url: string): boolean => {
        const tabId = urlToTabId.get(url);
        return tabId ? tabInfo.get(tabId)?.loading || false : false;
    };

    // Empty state - no tabs
    if (newsTabs.length === 0) {
        return (
            <div className="flex-1 flex flex-col bg-background overflow-hidden">
                <div className="h-10 bg-muted/40 flex items-center px-2 gap-1 border-b border-border/50 shrink-0">
                    <button
                        onClick={handleNewTab}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-cyan-400 hover:bg-cyan-500/10 rounded-md transition-colors"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        New Tab
                    </button>
                </div>
                <div className="flex-1 flex flex-col items-center justify-center bg-background">
                    <div className="p-4 bg-muted rounded-full mb-4">
                        <Search className="w-8 h-8 text-muted-foreground/40" />
                    </div>
                    <h3 className="text-foreground font-bold mb-2">Start Browsing</h3>
                    <p className="text-sm text-muted-foreground mb-4">Select an article from the left panel or open a new tab</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col bg-background overflow-hidden">
            {/* Tab Bar */}
            <div className="h-8 bg-muted/40 flex items-center px-2 gap-1 overflow-x-auto scrollbar-hide shrink-0">
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
                        {getLoadingForUrl(url) ? (
                            <Loader2 className="w-3 h-3 animate-spin text-cyan-400 shrink-0" />
                        ) : (
                            <Globe className="w-3 h-3 text-cyan-400 shrink-0" />
                        )}
                        <span className="truncate flex-1">{getTitleForUrl(url)}</span>
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

            {/* Browser Toolbar */}
            <div className="h-10 bg-card border-b border-border/50 flex items-center px-4 gap-3 shrink-0">
                {/* Navigation Buttons */}
                <div className="flex items-center gap-1">
                    <button
                        onClick={goBack}
                        disabled={!canGoBack}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground disabled:opacity-30"
                    >
                        <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                        onClick={goForward}
                        disabled={!canGoForward}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground disabled:opacity-30"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </button>
                    <button
                        onClick={reload}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground"
                    >
                        {isLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                            <RotateCw className="w-3.5 h-3.5" />
                        )}
                    </button>
                </div>

                {/* URL Bar */}
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

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                    {/* Zoom Controls */}
                    <div className="flex items-center bg-muted/50 rounded-md border border-border/50">
                        <button
                            onClick={() => setZoomLevel(Math.max(50, zoomLevel - 10))}
                            className="p-1 hover:bg-background rounded-l-md transition-colors text-muted-foreground"
                            title="Zoom Out"
                        >
                            <Minus className="w-3 h-3" />
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

                    {/* Add to Context */}
                    <button
                        onClick={addSelectionToContext}
                        className="flex items-center gap-1 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-cyan-400 hover:bg-cyan-500/10 rounded-md transition-colors"
                        title="Add selected text to context"
                    >
                        <PlusCircle className="w-3 h-3" />
                        Add to Context
                    </button>

                    {/* Open Externally */}
                    <button
                        onClick={() => activeNewsTab && window.open(activeNewsTab, '_blank')}
                        className="p-1.5 hover:bg-muted rounded-md transition-colors text-muted-foreground"
                        title="Open in default browser"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* Browser View Container */}
            <div
                ref={containerRef}
                className="flex-1 relative"
                style={{ minHeight: 200 }}
            />
        </div>
    );
};
