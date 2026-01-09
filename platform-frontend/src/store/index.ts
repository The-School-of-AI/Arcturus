import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
    Run,
    PlatformNode,
    PlatformEdge,
    Snapshot,
    RAGDocument,
    ChatMessage,
    Memory,
} from '../types';
import { applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from 'reactflow';
import { api, API_BASE } from '../lib/api';

// --- Slices Types ---

interface RunSlice {
    runs: Run[];
    currentRun: Run | null;
    addRun: (run: Run) => void;
    setCurrentRun: (runId: string) => void;
    updateRunStatus: (input: { id: string, status: Run['status'] }) => void;
    fetchRuns: () => Promise<void>;
    createNewRun: (query: string, model?: string) => Promise<void>;
    refreshCurrentRun: () => Promise<void>;
    pollingInterval: ReturnType<typeof setInterval> | null;
    startPolling: (runId: string) => void;
    stopPolling: () => void;
    deleteRun: (runId: string) => Promise<void>;
}

interface GraphSlice {
    nodes: PlatformNode[];
    edges: PlatformEdge[];
    selectedNodeId: string | null;
    setNodes: (nodes: PlatformNode[]) => void;
    setEdges: (edges: PlatformEdge[]) => void;
    onNodesChange: (changes: NodeChange[]) => void;
    onEdgesChange: (changes: EdgeChange[]) => void;
    selectNode: (nodeId: string | null) => void;
}

interface WorkspaceSlice {
    activeTab: 'code' | 'output' | 'web' | 'html';
    setActiveTab: (tab: 'code' | 'output' | 'web' | 'html') => void;
    codeContent: string;
    setCodeContent: (code: string) => void;
    webUrl: string;
    setWebUrl: (url: string) => void;
    logs: string[];
    addLog: (log: string) => void;
}

interface ReplaySlice {
    snapshots: Snapshot[];
    currentSnapshotIndex: number;
    isReplayMode: boolean;
    loadSnapshot: (index: number) => void;
    addSnapshot: (snapshot: Snapshot) => void;
    toggleReplayMode: (active: boolean) => void;
}

interface SettingsSlice {
    apiKey: string;
    setApiKey: (key: string) => void;
    mcpToolStates: Record<string, Record<string, boolean>>; // { serverName: { toolName: boolean } }
    toggleMcpTool: (serverName: string, toolName: string) => void;
    setMcpToolStates: (serverName: string, states: Record<string, boolean>) => void;
    theme: 'dark' | 'light'; // although we force dark mostly
    localModel: string;
    setLocalModel: (model: string) => void;
}

interface RagViewerSlice {
    viewMode: 'graph' | 'rag' | 'explorer';
    setViewMode: (mode: 'graph' | 'rag' | 'explorer') => void;
    sidebarTab: 'runs' | 'rag' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn' | 'settings';
    setSidebarTab: (tab: 'runs' | 'rag' | 'mcp' | 'remme' | 'explorer' | 'apps' | 'news' | 'learn' | 'settings') => void;
    openDocuments: RAGDocument[];
    activeDocumentId: string | null;
    openDocument: (doc: RAGDocument) => void;
    closeDocument: (docId: string) => void;
    closeAllDocuments: () => void;
    setActiveDocument: (docId: string) => void;
    ragSearchQuery: string;
    setRagSearchQuery: (query: string) => void;
    ragSearchResults: unknown[];
    setRagSearchResults: (results: unknown[]) => void;
    ragKeywordMatches: string[];
    setRagKeywordMatches: (matches: string[]) => void;
    addMessageToDocChat: (docId: string, message: ChatMessage) => void;
    updateMessageContent: (docId: string, messageId: string, newContent: string) => void;
    selectedContexts: string[];
    addSelectedContext: (text: string) => void;
    removeSelectedContext: (index: number) => void;
    clearSelectedContexts: () => void;
    selectedMcpServer: string | null;
    setSelectedMcpServer: (server: string | null) => void;
    settingsActiveTab: 'models' | 'rag' | 'agent' | 'prompts' | 'advanced';
    setSettingsActiveTab: (tab: 'models' | 'rag' | 'agent' | 'prompts' | 'advanced') => void;
    showRagInsights: boolean;
    setShowRagInsights: (show: boolean) => void;
    toggleRagInsights: () => void;

    // --- RAG UI States ---
    isRagNewFolderOpen: boolean;
    setIsRagNewFolderOpen: (open: boolean) => void;
    ragIndexingPath: string | null;
    setRagIndexingPath: (path: string | null) => void;
    ragIndexStatus: string | null;
    setRagIndexStatus: (status: string | null) => void;
    isRagIndexing: boolean;
    setIsRagIndexing: (indexing: boolean) => void;
    ragFiles: any[];
    setRagFiles: (files: any[]) => void;
    isRagLoading: boolean;
    setIsRagLoading: (loading: boolean) => void;
    fetchRagFiles: () => Promise<void>;

    // --- MCP UI States ---
    isMcpAddOpen: boolean;
    setIsMcpAddOpen: (open: boolean) => void;
    mcpServers: any[];
    setMcpServers: (servers: any[]) => void;
    fetchMcpServers: () => Promise<void>;

    // --- Remme UI States ---
    isRemmeAddOpen: boolean;
    setIsRemmeAddOpen: (open: boolean) => void;

    // --- News UI States ---
    isNewsAddOpen: boolean;
    setIsNewsAddOpen: (open: boolean) => void;
    newsViewMode: 'sources' | 'articles' | 'saved' | 'search';
    setNewsViewMode: (mode: 'sources' | 'articles' | 'saved' | 'search') => void;
    newsSearchQuery: string;
    setNewsSearchQuery: (query: string) => void;

    // --- Runs UI States ---
    isNewRunOpen: boolean;
    setIsNewRunOpen: (open: boolean) => void;
}

interface RemmeSlice {
    memories: Memory[];
    setMemories: (memories: Memory[]) => void;
    fetchMemories: () => Promise<void>;
    addMemory: (text: string, category?: string) => Promise<void>;
    deleteMemory: (id: string) => Promise<void>;
    cleanupDanglingMemories: () => Promise<void>;
}

interface AnalysisHistoryItem {
    id: string;
    name: string;
    path: string;
    timestamp: number;
    type: 'local' | 'github';
    flowData?: unknown;
}

import type { AppCard, SavedApp, LibraryComponent } from '../features/apps/types/app-types';
export type { AppCard, SavedApp, LibraryComponent };

interface LayoutItem {
    i: string;
    x: number;
    y: number;
    w: number;
    h: number;
    minW?: number;
    maxW?: number;
    minH?: number;
    maxH?: number;
    static?: boolean;
    [key: string]: unknown; // Allow additional properties from react-grid-layout
}

interface AppsSlice {
    appCards: AppCard[];
    appLayout: LayoutItem[];
    selectedAppCardId: string | null;
    selectedLibraryComponent: LibraryComponent | null; // For sidebar preview
    appsSidebarTab: 'apps' | 'components';
    setAppsSidebarTab: (tab: 'apps' | 'components') => void;
    savedApps: SavedApp[];
    editingAppId: string | null;
    lastSavedState: { cards: AppCard[], layout: LayoutItem[] } | null;
    setAppCards: (cards: AppCard[]) => void;
    addAppCard: (card: AppCard, layoutItem: LayoutItem) => void;
    removeAppCard: (id: string) => void;
    updateAppCardConfig: (id: string, config: any) => void;
    updateAppCardStyle: (id: string, style: any) => void;
    updateAppCardData: (id: string, data: any) => void;
    updateAppCardLabel: (id: string, label: string) => void;
    updateAppCardContext: (id: string, context: string) => void;
    setAppLayout: (layout: LayoutItem[]) => void;
    selectAppCard: (id: string | null) => void;
    selectLibraryComponent: (component: LibraryComponent | null) => void;
    fetchApps: () => Promise<void>;
    createNewApp: () => void;
    saveApp: (name?: string) => Promise<void>;
    renameApp: (id: string, newName: string) => Promise<void>;
    loadApp: (id: string, initialData?: SavedApp) => Promise<void>;
    revertAppChanges: () => void;
    deleteApp: (id: string) => Promise<void>;
    hydrateApp: (id: string, userPrompt?: string) => Promise<void>;
    generateApp: (name: string, prompt: string) => Promise<void>;
    isGeneratingApp: boolean;
    generateAppFromReport: (runId: string, nodeId?: string) => Promise<void>;
    loadShowcaseApp: () => Promise<void>;
    isAppViewMode: boolean;
    setIsAppViewMode: (isView: boolean) => void;
}

interface ExplorerSlice {
    explorerRootPath: string | null;
    setExplorerRootPath: (path: string | null) => void;
    explorerFiles: any[];
    setExplorerFiles: (files: any[]) => void;
    isAnalyzing: boolean;
    setIsAnalyzing: (analyzing: boolean) => void;
    flowData: any | null;
    setFlowData: (data: any | null) => void;
    selectedExplorerNodeId: string | null;
    setSelectedExplorerNodeId: (id: string | null) => void;
    analysisHistory: AnalysisHistoryItem[];
    addToHistory: (item: Omit<AnalysisHistoryItem, 'id' | 'timestamp'>) => void;
    removeFromHistory: (id: string) => void;
    updateHistoryItem: (path: string, data: Partial<AnalysisHistoryItem>) => void;
}

// --- Agent Test Mode Slice ---
interface AgentTestSlice {
    testMode: {
        active: boolean;
        nodeId: string | null;
        originalOutput: any;
        testOutput: any;
        executionResult: any; // Added executionResult
        isLoading: boolean;
        error: string | null;
    };
    runAgentTest: (runId: string, nodeId: string, overrideInput?: string) => Promise<void>;
    saveTestResult: (runId: string, nodeId: string) => Promise<void>;
    discardTestResult: () => void;
}

interface SavedArticle {
    id: string;
    title: string;
    url: string;
    savedAt: string;
}

interface NewsSlice {
    newsItems: any[];
    newsSources: any[];
    savedArticles: SavedArticle[];
    selectedNewsSourceId: string | null;
    newsTabs: string[];
    activeNewsTab: string | null;
    isNewsLoading: boolean;
    showNewsChatPanel: boolean;
    fetchNewsSources: () => Promise<void>;
    fetchNewsFeed: (sourceId?: string) => Promise<void>;
    setSelectedNewsSourceId: (id: string | null) => void;
    addNewsSource: (name: string, url: string) => Promise<void>;
    deleteNewsSource: (id: string) => Promise<void>;
    openNewsTab: (url: string) => void;
    closeNewsTab: (url: string) => void;
    closeAllNewsTabs: () => void;
    setActiveNewsTab: (url: string | null) => void;
    saveArticle: (title: string, url: string) => void;
    deleteSavedArticle: (id: string) => void;
    setShowNewsChatPanel: (show: boolean) => void;
    searchResults: any[];
    setSearchResults: (results: any[]) => void;
    clearSelection: () => void;
}

interface AppState extends RunSlice, GraphSlice, WorkspaceSlice, ReplaySlice, SettingsSlice, RagViewerSlice, RemmeSlice, ExplorerSlice, AppsSlice, AgentTestSlice, NewsSlice { }

export const useAppStore = create<AppState>()(
    persist(
        (set, get) => ({
            // Runs
            runs: [],
            currentRun: null,
            addRun: (run) => set((state) => ({ runs: [run, ...state.runs] })),
            setCurrentRun: (runId) => {
                const run = get().runs.find((r) => r.id === runId) || null;
                // Reset panel state when switching runs
                set({
                    currentRun: run,
                    selectedNodeId: null,
                    codeContent: '',
                    logs: [],
                    nodes: [],
                    edges: []
                });
                // If run exists, fetch its latest graph immediately
                if (run) {
                    get().refreshCurrentRun();
                }
            },
            updateRunStatus: ({ id, status }) => set((state) => ({
                runs: state.runs.map((r) => r.id === id ? { ...r, status } : r),
                currentRun: state.currentRun?.id === id ? { ...state.currentRun, status } : state.currentRun
            })),

            deleteRun: async (runId) => {
                try {
                    await api.deleteRun(runId);
                    set((state) => ({
                        runs: state.runs.filter((r) => r.id !== runId),
                        currentRun: state.currentRun?.id === runId ? null : state.currentRun
                    }));
                } catch (e) {
                    console.error("Failed to delete run", e);
                }
            },

            // API Actions
            fetchRuns: async () => {
                try {
                    const fetched = await api.getRuns();
                    // Enforce sorting
                    fetched.sort((a, b) => b.createdAt - a.createdAt);
                    set({ runs: fetched });
                } catch (e: any) {
                    console.error("Failed to fetch runs. Check if backend is running at http://localhost:8000 and if CORS is allowed.");
                    if (e.response) {
                        console.error("Response data:", e.response.data);
                        console.error("Response status:", e.response.status);
                    } else if (e.request) {
                        console.error("Request was made but no response received. This often indicates a CORS block or backend offline.");
                    } else {
                        console.error("Error setting up request:", e.message);
                    }
                }
            },

            createNewRun: async (query, model) => {
                try {
                    const res = await api.createRun(query, model);
                    const newRun: Run = {
                        id: res.id,
                        name: res.query,
                        createdAt: Date.now(),
                        status: 'running',
                        model: res.model || model || 'default',
                        ragEnabled: true
                    };
                    get().addRun(newRun);

                    // Reset Graph State Immediately
                    set({ nodes: [], edges: [], selectedNodeId: null, codeContent: '', logs: [] });

                    get().setCurrentRun(newRun.id);

                    // Start polling
                    get().startPolling(newRun.id);
                } catch (e) {
                    console.error("Failed to create run", e);
                }
            },

            refreshCurrentRun: async () => {
                const runId = get().currentRun?.id;
                if (!runId) return;
                try {
                    const graphData = await api.getRunGraph(runId);
                    set({
                        nodes: graphData.nodes,
                        edges: graphData.edges,
                        isReplayMode: false, // Ensure we are in live mode
                        currentSnapshotIndex: -1
                    });
                } catch (e) {
                    console.error("Failed to refresh graph", e);
                }
            },

            // Polling Logic
            pollingInterval: null,
            startPolling: (runId) => {
                // Clear existing first
                if (get().pollingInterval) clearInterval(get().pollingInterval!);

                const interval = setInterval(async () => {
                    await get().refreshCurrentRun();
                    await get().fetchRuns();

                    // Auto-stop if terminal state
                    const run = get().runs.find(r => r.id === runId);
                    if (run && (run.status === 'completed' || run.status === 'failed')) {
                        console.log(`Run ${runId} finished with status ${run.status}. Stopping polling.`);
                        get().stopPolling();
                    }
                }, 2000);
                set({ pollingInterval: interval });
            },
            stopPolling: () => {
                const interval = get().pollingInterval;
                if (interval) clearInterval(interval);
                set({ pollingInterval: null });
            },

            // Graph
            nodes: [],
            edges: [],
            selectedNodeId: null,
            setNodes: (nodes) => set({ nodes }),
            setEdges: (edges) => set({ edges }),
            onNodesChange: (changes) => set({
                nodes: applyNodeChanges(changes, get().nodes) as PlatformNode[]
            }),
            onEdgesChange: (changes) => set({
                edges: applyEdgeChanges(changes, get().edges)
            }),
            selectNode: (nodeId) => {
                const node = get().nodes.find(n => n.id === nodeId);
                set({ selectedNodeId: nodeId });

                if (node && node.data) {
                    // Populate panels
                    set({
                        codeContent: node.data.output || '// Waiting for output',
                        logs: [
                            `Status: ${node.data.status}`,
                            `Type: ${node.data.type}`,
                            node.data.error ? `Error: ${node.data.error}` : ''
                        ].filter(Boolean)
                    });
                }
            },

            // Workspace
            activeTab: 'code',
            setActiveTab: (tab) => set({ activeTab: tab }),
            codeContent: '// Agent code will appear here',
            setCodeContent: (code) => set({ codeContent: code }),
            webUrl: '',
            setWebUrl: (url) => set({ webUrl: url }),
            logs: [],
            addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),

            // Replay
            snapshots: [],
            currentSnapshotIndex: -1,
            isReplayMode: false,
            loadSnapshot: (index) => {
                const snapshot = get().snapshots[index];
                if (!snapshot) return;
                set({
                    currentSnapshotIndex: index,
                    nodes: snapshot.graphState.nodes,
                    edges: snapshot.graphState.edges,
                    codeContent: snapshot.codeContent,
                    webUrl: snapshot.webUrl || '',
                    // trigger other UI updates...
                });
            },
            addSnapshot: (snapshot) => set((state) => ({
                snapshots: [...state.snapshots, snapshot],
                currentSnapshotIndex: state.snapshots.length // pointing to new one
            })),
            toggleReplayMode: (active) => set({ isReplayMode: active }),

            // Settings
            apiKey: '',
            setApiKey: (key) => set({ apiKey: key }),
            mcpToolStates: {},
            toggleMcpTool: (server, tool) => {
                const state = get();
                const serverState = state.mcpToolStates[server] || {};
                const newState = !serverState[tool];

                // Optimistic update
                set(state => ({
                    mcpToolStates: {
                        ...state.mcpToolStates,
                        [server]: {
                            ...serverState,
                            [tool]: newState
                        }
                    }
                }));

                // Sync with backend
                api.post(`${API_BASE}/mcp/tool_state`, {
                    server_name: server,
                    tool_name: tool,
                    enabled: newState
                }).catch(e => console.error("Failed to sync tool state", e));
            },
            setMcpToolStates: (server, states) => {
                set(state => ({
                    mcpToolStates: {
                        ...state.mcpToolStates,
                        [server]: states
                    }
                }));
                // We probably shouldn't sync ALL states on load/init, only on user action
                // but if we wanted to enforce "Enable All" from button:
                // We can tackle that in the components if needed, or iterate here.
                // For now, let's keep setMcpToolStates local for hydration.
            },
            theme: 'dark',
            localModel: 'mistral:latest',
            setLocalModel: (model) => set({ localModel: model }),

            // RAG Viewer
            viewMode: 'graph',
            setViewMode: (mode) => set({ viewMode: mode }),
            openDocuments: [],
            activeDocumentId: null,
            openDocument: (doc) => {
                const alreadyOpen = get().openDocuments.find(d => d.id === doc.id);
                if (!alreadyOpen) {
                    set(state => ({
                        openDocuments: [...state.openDocuments, doc],
                        viewMode: 'rag',
                        activeDocumentId: doc.id
                    }));
                } else {
                    set({ activeDocumentId: doc.id, viewMode: 'rag' });
                }
            },
            closeDocument: (docId) => {
                const newDocs = get().openDocuments.filter(d => d.id !== docId);
                let newActiveId = get().activeDocumentId;
                if (newActiveId === docId) {
                    newActiveId = newDocs.length > 0 ? newDocs[newDocs.length - 1].id : null;
                }
                set({
                    openDocuments: newDocs,
                    activeDocumentId: newActiveId,
                    viewMode: newDocs.length === 0 ? 'graph' : 'rag'
                });
            },
            closeAllDocuments: () => set({
                openDocuments: [],
                activeDocumentId: null,
                viewMode: 'graph'
            }),
            setActiveDocument: (docId) => set({ activeDocumentId: docId, viewMode: 'rag' }),
            sidebarTab: 'runs',
            setSidebarTab: (tab) => set({ sidebarTab: tab }),
            settingsActiveTab: 'models',
            setSettingsActiveTab: (tab) => set({ settingsActiveTab: tab }),
            ragSearchQuery: '',
            setRagSearchQuery: (query) => set({ ragSearchQuery: query }),
            ragSearchResults: [],
            setRagSearchResults: (results) => set({ ragSearchResults: results }),
            ragKeywordMatches: [],
            setRagKeywordMatches: (matches) => set({ ragKeywordMatches: matches }),
            addMessageToDocChat: (docId, message) => set((state) => ({
                openDocuments: state.openDocuments.map((doc) =>
                    doc.id === docId
                        ? { ...doc, chatHistory: [...(doc.chatHistory || []), message] }
                        : doc
                )
            })),
            updateMessageContent: (docId, messageId, newContent) => set((state) => ({
                openDocuments: state.openDocuments.map((doc) =>
                    doc.id === docId
                        ? {
                            ...doc,
                            chatHistory: (doc.chatHistory || []).map(msg =>
                                msg.id === messageId ? { ...msg, content: newContent } : msg
                            )
                        }
                        : doc
                )
            })),
            selectedContexts: [],
            addSelectedContext: (text) => set((state) => ({
                selectedContexts: [...state.selectedContexts, text]
            })),
            removeSelectedContext: (index) => {
                const newContexts = get().selectedContexts.filter((_, i) => i !== index);
                // Close chat panel when all contexts are removed
                if (newContexts.length === 0) {
                    set({ selectedContexts: newContexts, showNewsChatPanel: false });
                } else {
                    set({ selectedContexts: newContexts });
                }
            },
            clearSelectedContexts: () => set({ selectedContexts: [], showNewsChatPanel: false }),
            selectedMcpServer: null,
            setSelectedMcpServer: (server) => set({ selectedMcpServer: server, sidebarTab: 'mcp' }),
            showRagInsights: false,
            setShowRagInsights: (show) => set({ showRagInsights: show }),
            toggleRagInsights: () => set(state => ({ showRagInsights: !state.showRagInsights })),

            // --- RAG UI States ---
            isRagNewFolderOpen: false,
            setIsRagNewFolderOpen: (open: boolean) => set({ isRagNewFolderOpen: open }),
            ragIndexingPath: null,
            setRagIndexingPath: (path: string | null) => set({ ragIndexingPath: path }),
            ragIndexStatus: null,
            setRagIndexStatus: (status: string | null) => set({ ragIndexStatus: status }),
            isRagIndexing: false,
            setIsRagIndexing: (indexing: boolean) => set({ isRagIndexing: indexing }),
            ragFiles: [],
            setRagFiles: (files: any[]) => set({ ragFiles: files }),
            isRagLoading: false,
            setIsRagLoading: (loading: boolean) => set({ isRagLoading: loading }),
            fetchRagFiles: async () => {
                set({ isRagLoading: true });
                try {
                    const res = await api.get(`${API_BASE}/rag/documents`);
                    set({ ragFiles: res.data.files });
                } catch (e) {
                    console.error("Failed to fetch RAG docs", e);
                } finally {
                    set({ isRagLoading: false });
                }
            },

            // --- MCP UI States ---
            isMcpAddOpen: false,
            setIsMcpAddOpen: (open: boolean) => set({ isMcpAddOpen: open }),
            mcpServers: [],
            setMcpServers: (servers: any[]) => set({ mcpServers: servers }),
            fetchMcpServers: async () => {
                try {
                    const res = await api.get(`${API_BASE}/mcp/servers`);
                    set({ mcpServers: res.data.servers });
                } catch (e) {
                    console.error("Failed to fetch MCP servers", e);
                }
            },

            // --- Remme UI States ---
            isRemmeAddOpen: false,
            setIsRemmeAddOpen: (open: boolean) => set({ isRemmeAddOpen: open }),

            // --- News UI States ---
            isNewsAddOpen: false,
            setIsNewsAddOpen: (open: boolean) => set({ isNewsAddOpen: open }),
            newsViewMode: 'sources',
            setNewsViewMode: (mode) => set({ newsViewMode: mode }),
            newsSearchQuery: '',
            setNewsSearchQuery: (query) => set({ newsSearchQuery: query }),

            // --- Runs UI States ---
            isNewRunOpen: false,
            setIsNewRunOpen: (open: boolean) => set({ isNewRunOpen: open }),

            // --- Remme Slice ---
            memories: [],
            setMemories: (memories) => set({ memories }),
            fetchMemories: async () => {
                try {
                    const res = await api.get(`${API_BASE}/remme/memories`);
                    set({ memories: res.data.memories });
                } catch (e) {
                    console.error("Failed to fetch memories", e);
                }
            },
            addMemory: async (text, category = "general") => {
                try {
                    await api.post(`${API_BASE}/remme/add`, { text, category });
                    get().fetchMemories();
                } catch (e) {
                    console.error("Failed to add memory", e);
                }
            },
            deleteMemory: async (id) => {
                try {
                    await api.delete(`${API_BASE}/remme/memories/${id}`);
                    get().fetchMemories();
                } catch (e) {
                    console.error("Failed to delete memory", e);
                }
            },
            cleanupDanglingMemories: async () => {
                try {
                    await api.post(`${API_BASE}/remme/cleanup_dangling`);
                    get().fetchMemories();
                } catch (e) {
                    console.error("Failed to cleanup dangling memories", e);
                }
            },

            // --- Explorer Slice ---
            explorerRootPath: null,
            setExplorerRootPath: (path) => set({ explorerRootPath: path }),
            explorerFiles: [],
            setExplorerFiles: (files) => set({ explorerFiles: files }),
            isAnalyzing: false,
            setIsAnalyzing: (analyzing) => set({ isAnalyzing: analyzing }),
            flowData: null,
            setFlowData: (data) => set({ flowData: data, viewMode: 'explorer' }),
            selectedExplorerNodeId: null,
            setSelectedExplorerNodeId: (id) => set({ selectedExplorerNodeId: id }),
            analysisHistory: [],
            addToHistory: (item) => set((state) => {
                const newItem: AnalysisHistoryItem = {
                    ...item,
                    id: Math.random().toString(36).substr(2, 9),
                    timestamp: Date.now()
                };
                // Pre-filter duplicates
                const filtered = state.analysisHistory.filter(h => h.path !== item.path);
                return { analysisHistory: [newItem, ...filtered].slice(0, 10) };
            }),
            removeFromHistory: (id) => set((state) => ({
                analysisHistory: state.analysisHistory.filter(h => h.id !== id)
            })),
            updateHistoryItem: (path, data) => set((state) => ({
                analysisHistory: state.analysisHistory.map(h =>
                    h.path === path ? { ...h, ...data } : h
                )
            })),

            // --- Apps Slice ---
            appCards: [],
            appLayout: [],
            selectedAppCardId: null,
            selectedLibraryComponent: null,
            appsSidebarTab: 'apps',
            setAppsSidebarTab: (tab) => set({ appsSidebarTab: tab }),
            savedApps: [],
            editingAppId: null,
            lastSavedState: null,
            setAppCards: (appCards) => set({ appCards }),
            addAppCard: (card, layoutItem) => set((state) => ({
                appCards: [...state.appCards, card],
                appLayout: [...state.appLayout, { ...layoutItem, i: card.id }],
                selectedAppCardId: card.id
            })),
            removeAppCard: (id) => set((state) => ({
                appCards: state.appCards.filter(c => c.id !== id),
                appLayout: state.appLayout.filter(l => l.i !== id),
                selectedAppCardId: state.selectedAppCardId === id ? null : state.selectedAppCardId
            })),
            updateAppCardConfig: (id, config) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, config: { ...c.config, ...config } } : c)
            })),
            updateAppCardStyle: (id, style) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, style: { ...c.style, ...style } } : c)
            })),
            updateAppCardData: (id, data) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, data: { ...c.data, ...data } } : c)
            })),
            updateAppCardLabel: (id, label) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, label } : c)
            })),
            updateAppCardContext: (id, context) => set((state) => ({
                appCards: state.appCards.map(c => c.id === id ? { ...c, context } : c)
            })),
            setAppLayout: (appLayout) => set({ appLayout }),
            selectAppCard: (id) => set({ selectedAppCardId: id, selectedLibraryComponent: null }), // Clear lib selection when canvas card selected
            selectLibraryComponent: (component) => set({ selectedLibraryComponent: component, selectedAppCardId: null }), // Clear canvas selection when lib item selected

            fetchApps: async () => {
                try {
                    const apps = await api.getApps();
                    set({ savedApps: apps as SavedApp[] });
                } catch (e) {
                    console.error("Failed to fetch apps", e);
                }
            },

            createNewApp: () => set({
                appCards: [],
                appLayout: [],
                editingAppId: null,
                lastSavedState: null,
                selectedAppCardId: null
            }),

            saveApp: async (name) => {
                const state = get();

                let appId = state.editingAppId;
                let appName = name;

                if (!appId) {
                    appId = `app-${Date.now()}`;
                    appName = name || 'Untitled App';
                } else {
                    const existing = state.savedApps.find(a => a.id === appId);
                    if (!appName && existing) appName = existing.name;
                    if (!appName) appName = 'Untitled App';
                }

                const appData: SavedApp = {
                    id: appId,
                    name: appName || 'Untitled',
                    lastModified: Date.now(),
                    cards: state.appCards,
                    layout: state.appLayout
                };

                try {
                    await api.saveApp(appData);
                    set((s) => {
                        const exists = s.savedApps.find(a => a.id === appId);
                        let newSavedApps;
                        if (exists) {
                            newSavedApps = s.savedApps.map(a => a.id === appId ? appData : a);
                        } else {
                            newSavedApps = [appData, ...s.savedApps];
                        }

                        return {
                            savedApps: newSavedApps,
                            editingAppId: appId,
                            lastSavedState: { cards: appData.cards, layout: appData.layout }
                        };
                    });
                } catch (e) {
                    console.error("Failed to save app", e);
                }
            },
            renameApp: async (id, newName) => {
                const state = get();
                const app = state.savedApps.find(a => a.id === id);
                if (!app) return;

                const updatedApp = { ...app, name: newName, lastModified: Date.now() };

                try {
                    await api.renameApp(id, newName);
                    set((s) => ({
                        savedApps: s.savedApps.map(a => a.id === id ? updatedApp : a)
                    }));
                } catch (e) {
                    console.error("Failed to rename app", e);
                }
            },

            loadApp: async (id, initialData) => {
                if (initialData) {
                    set({
                        appCards: initialData.cards || [],
                        appLayout: initialData.layout || [],
                        editingAppId: id,
                        lastSavedState: { cards: initialData.cards || [], layout: initialData.layout || [] },
                        selectedAppCardId: null
                    });
                }

                try {
                    const fullApp = await api.getApp(id);
                    set({
                        appCards: fullApp.cards || [],
                        appLayout: fullApp.layout || [],
                        editingAppId: id,
                        lastSavedState: { cards: fullApp.cards || [], layout: fullApp.layout || [] },
                        selectedAppCardId: null
                    });
                } catch (e) {
                    console.error("Failed to load app", e);
                }
            },

            revertAppChanges: () => set((state) => {
                if (state.lastSavedState) {
                    return {
                        appCards: state.lastSavedState.cards,
                        appLayout: state.lastSavedState.layout,
                        selectedAppCardId: null
                    };
                } else {
                    return {
                        appCards: [],
                        appLayout: [],
                        selectedAppCardId: null
                    };
                }
            }),

            deleteApp: async (id) => {
                try {
                    await api.deleteApp(id);
                    set((state) => ({
                        savedApps: state.savedApps.filter(a => a.id !== id),
                        editingAppId: state.editingAppId === id ? null : state.editingAppId,
                        lastSavedState: state.editingAppId === id ? null : state.lastSavedState
                    }));
                } catch (e) {
                    console.error("Failed to delete app", e);
                }
            },

            hydrateApp: async (id, userPrompt) => {
                try {
                    const result = await api.hydrateApp(id, userPrompt);
                    if (result.status === 'success' && result.data) {
                        // Update local state with hydrated data
                        set((state) => ({
                            appCards: result.data.cards || state.appCards,
                            appLayout: result.data.layout || state.appLayout
                        }));
                        // Refresh savedApps list
                        await get().fetchApps();
                    }
                } catch (e) {
                    console.error("Failed to hydrate app", e);
                    throw e;
                }
            },

            generateApp: async (prompt) => {
                try {
                    // Create a pseudo-run for app generation tracking if needed, 
                    // or just call the API directly.
                    // For now, simple direct call as per previous implementation logic
                    // Pass a default name based on prompt or generic
                    const appName = "Generated App " + new Date().toLocaleTimeString();
                    const result = await api.generateApp(appName, prompt);

                    if (result.status === 'success' && result.data) {
                        await get().loadApp(result.id, result.data);
                    }
                } catch (e) {
                    console.error("Failed to generate app", e);
                    throw e;
                }
            },

            isGeneratingApp: false,

            generateAppFromReport: async (runId, nodeId) => {
                if (get().isGeneratingApp) return;
                set({ isGeneratingApp: true });

                try {
                    const currentRunId = runId || get().currentRun?.id;
                    if (!currentRunId) {
                        alert("No active run found.");
                        set({ isGeneratingApp: false });
                        return;
                    }

                    // Show progress alert
                    console.log("[BuildApp] Starting app generation...");

                    // 1. Fetch Node Output (Report) + Globals
                    const graphData = await api.getRunGraph(currentRunId);

                    // Locate Formatter Node - check both type and label
                    let targetNodeId = nodeId;
                    if (!targetNodeId) {
                        const formatterNode = graphData.nodes.find((n: any) => {
                            const isFormatter = n.data?.type === 'FormatterAgent' ||
                                n.data?.label?.toLowerCase().includes('formatter');
                            const isCompleted = n.data?.status === 'completed';
                            console.log(`[BuildApp] Checking node ${n.id}: type=${n.data?.type}, label=${n.data?.label}, status=${n.data?.status}, isFormatter=${isFormatter}, isCompleted=${isCompleted}`);
                            return isFormatter && isCompleted;
                        });
                        targetNodeId = formatterNode?.id;

                        if (formatterNode) {
                            console.log(`[BuildApp] Found formatter node: ${targetNodeId}`);
                        }
                    }

                    if (!targetNodeId) {
                        const types = graphData.nodes.map((n: any) => `${n.id}: type=${n.data?.type}, label=${n.data?.label}, status=${n.data?.status}`).join('\n');
                        console.error("[BuildApp] Available nodes:\n" + types);
                        alert("No completed Formatter Agent found in this run to generate from.");
                        set({ isGeneratingApp: false });
                        return;
                    }

                    const node = graphData.nodes.find((n: any) => n.id === targetNodeId);

                    if (!node || !node.data.output) {
                        alert("Report data not found.");
                        set({ isGeneratingApp: false });
                        return;
                    }

                    // Extract report content
                    const output = node.data.output;
                    let reportContent = "";

                    if (typeof output === 'string') {
                        try {
                            const parsed = JSON.parse(output);
                            const reportKey = Object.keys(parsed).find(k => k.startsWith("formatted_report"));
                            if (reportKey) reportContent = parsed[reportKey];
                            else if (parsed.report) reportContent = parsed.report;
                            else reportContent = output;
                        } catch {
                            reportContent = output;
                        }
                    } else {
                        const reportKey = Object.keys(output).find(k => k.startsWith("formatted_report"));
                        if (reportKey) {
                            reportContent = (output as any)[reportKey];
                        } else if ((output as any).report) {
                            reportContent = (output as any).report;
                        } else {
                            reportContent = JSON.stringify(output);
                        }
                    }

                    console.log(`[BuildApp] Report content length: ${reportContent.length} chars`);

                    // Fetch Globals
                    let globalsJson = {};
                    if (graphData.graph && graphData.graph.globals_schema) {
                        globalsJson = graphData.graph.globals_schema;
                    }

                    const payload = {
                        report_content: reportContent,
                        globals_json: globalsJson
                    };

                    // Trigger Generation
                    console.log("[BuildApp] Calling backend to generate app...");
                    const res = await api.post(`${API_BASE}/apps/generate_from_report`, payload);

                    if (res.data.status === 'success') {
                        console.log(`[BuildApp] App generated successfully: ${res.data.id}`);
                        await get().fetchApps();
                        // Show success message briefly
                        alert(`App generated successfully! Redirecting...`);
                        // Switch to apps tab and load the app
                        get().setSidebarTab('apps');
                        setTimeout(() => {
                            get().loadApp(res.data.id, res.data.data);
                        }, 100);
                    }

                } catch (e) {
                    console.error("[BuildApp] Generate App Failed", e);
                    alert("Failed to generate app: " + (e as any).message);
                } finally {
                    set({ isGeneratingApp: false });
                }
            },

            isAppViewMode: false,
            setIsAppViewMode: (isView) => set({ isAppViewMode: isView }),

            loadShowcaseApp: async () => {
                const showcaseId = "showcase-demo";
                const showcaseData: SavedApp = {
                    id: showcaseId,
                    name: "VerusIQ Showcase",
                    lastModified: Date.now(),
                    cards: [
                        { id: 'h1', type: 'header', label: 'Market Overview', config: { bold: true }, style: { showBorder: false }, data: { text: "Market Overview" } },
                        { id: 'd1', type: 'date_picker', label: 'Period', config: { showLabel: true }, style: {}, data: { label: "Period", startDate: "2024-01-01", endDate: "2024-12-31" } },
                        { id: 'm1', type: 'metric', label: 'Revenue', config: { showTrend: true }, style: {}, data: { value: "$4.2M", change: 12.5, trend: "up" } },
                        { id: 'm2', type: 'metric', label: 'Active Users', config: { showTrend: true }, style: {}, data: { value: "14.5K", change: 8.2, trend: "up" } },
                        { id: 'm3', type: 'metric', label: 'Churn Rate', config: { showTrend: true }, style: {}, data: { value: "2.1%", change: -0.5, trend: "down" } },
                        { id: 'c1', type: 'line_chart', label: 'Revenue Trend', config: { showTitle: true, showLegend: true }, style: { borderRadius: 12 }, data: { title: "Monthly Revenue", points: [{ "x": "Jan", "y": 120 }, { "x": "Feb", "y": 135 }, { "x": "Mar", "y": 125 }, { "x": "Apr", "y": 145 }, { "x": "May", "y": 160 }, { "x": "Jun", "y": 155 }] } },
                        { id: 'c2', type: 'bar_chart', label: 'User Acquisition', config: { showTitle: true }, style: { borderRadius: 12 }, data: { title: "Sources", points: [{ "x": "Organic", "y": 450 }, { "x": "Ads", "y": 320 }, { "x": "Referral", "y": 210 }, { "x": "Social", "y": 180 }] } },
                        { id: 't1', type: 'switch', label: 'Live Mode', config: { showLabel: true }, style: {}, data: { label: "Live Updates", checked: "true" } },
                        { id: 's1', type: 'slider', label: 'Risk Tolerance', config: { showLabel: true }, style: {}, data: { label: "Risk Lvl", min: 0, max: 100, value: 65 } },
                        { id: 'grid1', type: 'stats_grid', label: 'Key KPIs', config: { showTitle: true }, style: {}, data: { stats: [{ "name": "LTV", "value": "$450", "change": "+5%" }, { "name": "CAC", "value": "$120", "change": "-2%" }] } }
                    ],
                    layout: [
                        { i: 'h1', x: 0, y: 0, w: 9, h: 2 },
                        { i: 'd1', x: 9, y: 0, w: 3, h: 2 },
                        { i: 'm1', x: 0, y: 2, w: 4, h: 3 },
                        { i: 'm2', x: 4, y: 2, w: 4, h: 3 },
                        { i: 'm3', x: 8, y: 2, w: 4, h: 3 },
                        { i: 'c1', x: 0, y: 5, w: 8, h: 8 },
                        { i: 't1', x: 8, y: 5, w: 4, h: 2 },
                        { i: 's1', x: 8, y: 7, w: 4, h: 2 },
                        { i: 'grid1', x: 8, y: 9, w: 4, h: 4 },
                        { i: 'c2', x: 0, y: 13, w: 12, h: 6 }
                    ]
                };

                try {
                    await api.saveApp(showcaseData);
                    await get().fetchApps();
                    await get().loadApp(showcaseId);
                    set({ sidebarTab: 'apps' });
                } catch (e) {
                    console.error("Failed to generate showcase", e);
                }
            },

            // --- Agent Test Slice ---
            testMode: {
                active: false,
                nodeId: null,
                originalOutput: null,
                testOutput: null,
                executionResult: null,
                isLoading: false,
                error: null
            },

            runAgentTest: async (runId: string, nodeId: string, overrideInput?: string) => {
                set({
                    testMode: {
                        active: true,
                        nodeId,
                        originalOutput: null,
                        testOutput: null,
                        executionResult: null,
                        isLoading: true,
                        error: null
                    }
                });

                try {
                    const response = await api.post(`${API_BASE}/runs/${runId}/agent/${nodeId}/test`, {
                        input: overrideInput
                    });
                    const data = response.data;

                    if (data.status === 'success') {
                        set({
                            testMode: {
                                active: true,
                                nodeId,
                                originalOutput: data.original_output,
                                testOutput: data.test_output,
                                executionResult: data.execution_result,
                                isLoading: false,
                                error: null
                            }
                        });
                    } else {
                        set({
                            testMode: {
                                active: true,
                                nodeId,
                                originalOutput: null,
                                testOutput: null,
                                executionResult: null,
                                isLoading: false,
                                error: data.error || 'Agent test failed'
                            }
                        });
                    }
                } catch (e: any) {
                    console.error("Agent test failed:", e);
                    set({
                        testMode: {
                            active: true,
                            nodeId,
                            originalOutput: null,
                            testOutput: null,
                            executionResult: null,
                            isLoading: false,
                            error: e.response?.data?.detail || e.message || 'Unknown error'
                        }
                    });
                }
            },

            saveTestResult: async (runId: string, nodeId: string) => {
                const { testMode } = get();
                if (!testMode.testOutput) return;

                try {
                    await api.post(`${API_BASE}/runs/${runId}/agent/${nodeId}/save`, {
                        output: testMode.testOutput,
                        execution_result: testMode.executionResult
                    });

                    // Refresh the current run to show updated data
                    await get().refreshCurrentRun();

                    // Exit test mode
                    set({
                        testMode: {
                            active: false,
                            nodeId: null,
                            originalOutput: null,
                            testOutput: null,
                            executionResult: null,
                            isLoading: false,
                            error: null
                        }
                    });
                } catch (e) {
                    console.error("Failed to save test result", e);
                }
            },

            discardTestResult: () => {
                set({
                    testMode: {
                        active: false,
                        nodeId: null,
                        originalOutput: null,
                        testOutput: null,
                        executionResult: null,
                        isLoading: false,
                        error: null
                    }
                });
            },

            // --- News Slice ---
            newsItems: [],
            newsSources: [],
            selectedNewsSourceId: null,
            newsTabs: [],
            activeNewsTab: null,
            isNewsLoading: false,
            showNewsChatPanel: false,
            searchResults: [],

            fetchNewsSources: async () => {
                try {
                    const res = await api.get(`${API_BASE}/news/sources`);
                    set({ newsSources: res.data.sources || [] });
                } catch (e) {
                    console.error("Failed to fetch news sources", e);
                }
            },

            fetchNewsFeed: async (sourceId) => {
                set({ isNewsLoading: true });
                try {
                    const endpoint = sourceId
                        ? `${API_BASE}/news/feed?source_id=${sourceId}`
                        : `${API_BASE}/news/feed`;
                    const res = await api.get(endpoint);
                    set({ newsItems: res.data.items || [], isNewsLoading: false });
                } catch (e) {
                    console.error("Failed to fetch news feed", e);
                    set({ isNewsLoading: false });
                }
            },

            setSelectedNewsSourceId: (id) => set({ selectedNewsSourceId: id }),

            addNewsSource: async (name, url) => {
                try {
                    await api.post(`${API_BASE}/news/sources`, { name, url });
                    get().fetchNewsSources();
                } catch (e) {
                    console.error("Failed to add news source", e);
                }
            },

            setShowNewsChatPanel: (show) => set({ showNewsChatPanel: show }),

            setSearchResults: (results) => set({ searchResults: results }),

            clearSelection: () => set({
                selectedNodeId: null,
                selectedAppCardId: null,
                selectedExplorerNodeId: null,
                activeDocumentId: null,
                selectedMcpServer: null,
                selectedLibraryComponent: null,
                showRagInsights: false,
            }),

            deleteNewsSource: async (id) => {
                try {
                    await api.delete(`${API_BASE}/news/sources/${id}`);
                    get().fetchNewsSources();
                } catch (e) {
                    console.error("Failed to delete news source", e);
                }
            },

            openNewsTab: (url) => {
                const tabs = get().newsTabs;
                if (!tabs.includes(url)) {
                    set({ newsTabs: [...tabs, url], activeNewsTab: url });
                } else {
                    set({ activeNewsTab: url });
                }
            },

            closeNewsTab: (url) => {
                const tabs = get().newsTabs.filter(t => t !== url);
                let active = get().activeNewsTab;
                if (active === url) {
                    active = tabs.length > 0 ? tabs[tabs.length - 1] : null;
                }
                // Also clear selected contexts when closing a tab
                set({ newsTabs: tabs, activeNewsTab: active, selectedContexts: [] });
            },

            closeAllNewsTabs: () => set({ newsTabs: [], activeNewsTab: null, selectedContexts: [] }),
            setActiveNewsTab: (url) => set({ activeNewsTab: url }),

            // Saved articles
            savedArticles: [],
            saveArticle: (title, url) => {
                const id = `saved_${Date.now()}`;
                const article: SavedArticle = {
                    id,
                    title,
                    url,
                    savedAt: new Date().toISOString()
                };
                set({ savedArticles: [...get().savedArticles, article] });
            },
            deleteSavedArticle: (id) => {
                set({ savedArticles: get().savedArticles.filter(a => a.id !== id) });
            },
        }),
        {
            name: 'agent-platform-storage',
            partialize: (state) => ({
                // Only persist user settings, not runs (which should come fresh from API)
                apiKey: state.apiKey,
                mcpToolStates: state.mcpToolStates,
                localModel: state.localModel,
                viewMode: state.viewMode,
                sidebarTab: state.sidebarTab,
                activeDocumentId: state.activeDocumentId,
                openDocuments: state.openDocuments,
                selectedContexts: state.selectedContexts,
                analysisHistory: state.analysisHistory,
                appCards: state.appCards,
                appLayout: state.appLayout,
                savedApps: state.savedApps,
                editingAppId: state.editingAppId,
                lastSavedState: state.lastSavedState,
                isAppViewMode: state.isAppViewMode,
                newsSources: state.newsSources,
                newsItems: state.newsItems, // PERSIST NEWS ITEMS for faster reload
                savedArticles: state.savedArticles, // PERSIST SAVED ARTICLES
            }),
        }
    )
);
