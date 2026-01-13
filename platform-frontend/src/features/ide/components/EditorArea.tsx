import React, { useEffect } from 'react';
import Editor, { loader, DiffEditor } from '@monaco-editor/react';
import { useAppStore } from '@/store';
// Removed unused useIdeStore import to fix potential lint if not used, or keep if needed. It was imported in previous version.
// Checking previous file content, useIdeStore was unused.
import { FileCode, Loader2, X, FileText, Code2, ExternalLink, Save, CheckCircle2 } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/components/theme';
import { Button } from '@/components/ui/button';
import { useState, useCallback } from 'react';

// Configure Monaco to use local resources if needed, or just standard setup
loader.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs' } });

export const EditorArea: React.FC = () => {
    const {
        openDocuments,
        activeDocumentId,
        updateDocumentContent,
        setActiveDocument,
        closeDocument,
        closeAllDocuments
    } = useAppStore();

    const { theme } = useTheme();
    const [isSaving, setIsSaving] = useState(false);
    const [lastSaved, setLastSaved] = useState<string | null>(null);

    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);

    const handleSave = useCallback(async () => {
        if (!activeDoc || activeDoc.content === undefined) return;

        setIsSaving(true);
        try {
            const result = await window.electronAPI.invoke('fs:writeFile', {
                path: activeDoc.id,
                content: activeDoc.content
            });

            if (result) {
                setLastSaved(activeDoc.id);
                setTimeout(() => setLastSaved(null), 2000);
            }
        } catch (error) {
            console.error('Failed to save file:', error);
        } finally {
            setIsSaving(false);
        }
    }, [activeDoc, activeDoc?.id, activeDoc?.content]);

    // Keyboard shortcut for saving
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                handleSave();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handleSave]);

    // Fetch content if missing
    useEffect(() => {
        if (!activeDoc) return;
        if (activeDoc.content === undefined && activeDoc.type !== 'folder') {
            const fetchContent = async () => {
                try {
                    const res = await axios.get(`${API_BASE}/rag/document_content`, {
                        params: { path: activeDoc.id }
                    });
                    // Handle various return shapes (string or json object)
                    const content = res.data.content !== undefined
                        ? (typeof res.data.content === 'string' ? res.data.content : JSON.stringify(res.data.content, null, 2))
                        : (typeof res.data === 'string' ? res.data : '');

                    updateDocumentContent(activeDoc.id, content);
                } catch (e) {
                    console.error("Failed to load document content", e);
                    updateDocumentContent(activeDoc.id, "// Failed to load content.\n// The file might be binary or inaccessible.");
                }
            };
            fetchContent();
        }
    }, [activeDoc?.id, activeDoc?.content]);

    // Custom Monaco Theme to match RAG/App Theme
    const handleEditorDidMount = (editor: any, monaco: any) => {
        // Dark Theme
        monaco.editor.defineTheme('arcturus-dark', {
            base: 'vs-dark',
            inherit: true,

            // Token colors (optional but makes it feel "yours")
            rules: [
                { token: 'comment', foreground: '6B7A90' },          // muted blue-gray
                { token: 'keyword', foreground: '4588F1' },          // Arcturus blue
                { token: 'delimiter', foreground: '9AA4B2' },
                { token: 'number', foreground: '7AA2F7' },           // soft periwinkle
                { token: 'string', foreground: '7DD3FC' },           // icy blue
                { token: 'type.identifier', foreground: '93C5FD' },
                { token: 'function', foreground: '60A5FA' },
            ],

            colors: {
                // Transparent so your glass/gradient shows through
                'editor.background': '#00000000',

                // Core text/cursor
                'editor.foreground': '#D6E0F0',
                'editorCursor.foreground': '#60A5FA',

                // Current line + selection (blue-tinted, not gray)
                'editor.lineHighlightBackground': '#4588F112',          // ~7% blue tint
                'editor.selectionBackground': '#1E3A8A66',              // deep blue selection
                'editor.inactiveSelectionBackground': '#1E3A8A33',

                // Line numbers
                'editorLineNumber.foreground': '#4B5563',
                'editorLineNumber.activeForeground': '#93C5FD',

                // Guides / brackets
                'editorIndentGuide.background1': '#1F2A44',
                'editorIndentGuide.activeBackground1': '#2E5493',
                'editorBracketMatch.background': '#4588F120',
                'editorBracketMatch.border': '#4588F180',

                // Find / match highlights
                'editor.findMatchBackground': '#4588F136',
                'editor.findMatchHighlightBackground': '#4588F11F',
                'editor.findRangeHighlightBackground': '#4588F114',

                // Widgets (hover, suggest) to match your panels
                'editorWidget.background': '#0B1220',
                'editorWidget.border': '#1F304F',
                'editorHoverWidget.background': '#0B1220',
                'editorHoverWidget.border': '#1F304F',
                'editorSuggestWidget.background': '#0B1220',
                'editorSuggestWidget.border': '#1F304F',
                'editorSuggestWidget.selectedBackground': '#4588F11A',

                // Scrollbar subtle blue glow
                'scrollbarSlider.background': '#4588F118',
                'scrollbarSlider.hoverBackground': '#4588F126',
                'scrollbarSlider.activeBackground': '#4588F133',

                // Minimap + gutter
                'minimap.background': '#00000000',
                'editorGutter.background': '#00000000',
            },
        });

        // Light Theme
        monaco.editor.defineTheme('arcturus-light', {
            base: 'vs',
            inherit: true,
            rules: [],
            colors: {
                'editor.background': '#ffffff00', // Transparent
                'editor.lineHighlightBackground': '#0000000a',
                'editorLineNumber.foreground': '#a1a1aa',
                'editor.selectionBackground': '#add6ff',
                'editor.inactiveSelectionBackground': '#e5e7eb',
            }
        });
    };

    const getLanguage = (ext: string) => {
        const mapping: Record<string, string> = {
            'js': 'javascript',
            'jsx': 'javascript',
            'mjs': 'javascript',
            'cjs': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'py': 'python',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'toml': 'toml',
            'html': 'html',
            'htm': 'html',
            'css': 'css',
            'scss': 'scss',
            'md': 'markdown',
            'markdown': 'markdown',
            'sh': 'shell',
            'bash': 'shell',
            'sql': 'sql',
            'xml': 'xml',
            'env': 'properties'
        };
        return mapping[ext.toLowerCase()] || 'plaintext';
    };

    if (!activeDoc) {
        return (
            <div className="h-full w-full flex flex-col items-center justify-center bg-transparent text-muted-foreground space-y-4">
                <div className="relative">
                    <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full" />
                    <div className="relative p-8 rounded-[2rem] bg-card/50 border border-border/50 shadow-inner backdrop-blur-sm">
                        <Code2 className="w-16 h-16 text-primary/40" />
                    </div>
                </div>
                <div className="text-center space-y-2">
                    <h3 className="text-lg font-bold text-foreground tracking-tight">Editor Empty</h3>
                    <p className="text-xs opacity-50">Select a file from the Explorer to start editing</p>
                </div>
            </div>
        );
    }

    return (
        <div className={cn("h-full w-full flex flex-col backdrop-blur-sm transition-colors duration-300", theme === 'dark' ? "bg-[#1e1e1e]/80" : "bg-white/80")}>
            {/* Tab Bar - Browser Style (Matches DocumentViewer) */}
            <div className="flex items-center justify-between border-b border-border bg-muted/30 pr-4 shrink-0 h-10">
                <div className="flex items-center gap-[1px] px-2 h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {openDocuments.map(doc => (
                        <div
                            key={doc.id}
                            onClick={() => setActiveDocument(doc.id)}
                            className={cn(
                                "group flex items-center gap-1.5 px-3 h-9 mt-auto rounded-t-lg transition-all cursor-pointer min-w-[100px] max-w-[200px] border-x border-t border-transparent relative select-none",
                                activeDocumentId === doc.id
                                    ? (theme === 'dark'
                                        ? "bg-[#1e1e1e]/80 border-border text-foreground z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-[#1e1e1e]"
                                        : "bg-white border-border text-foreground z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-white shadow-sm")
                                    : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
                            )}
                        >
                            {/* We keep the icon logic same or use getLanguage for better icons later */}
                            <FileCode className="w-3.5 h-3.5 shrink-0 text-blue-400" />
                            <span className="text-[11px] font-medium truncate flex-1">{doc.title}</span>
                            <button
                                onClick={(e) => { e.stopPropagation(); closeDocument(doc.id); }}
                                className="p-0.5 rounded-md hover:bg-black/5 dark:hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                </div>
                <div className="flex items-center gap-2">
                    {lastSaved === activeDocumentId && (
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-green-500/10 text-green-500 text-[10px] font-medium animate-in fade-in slide-in-from-right-2">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Saved</span>
                        </div>
                    )}
                    <button
                        onClick={handleSave}
                        disabled={isSaving || !activeDoc}
                        className={cn(
                            "p-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50 transition-all",
                            isSaving && "animate-pulse"
                        )}
                        title="Save (Ctrl+S)"
                    >
                        <Save className="w-4 h-4 text-muted-foreground hover:text-foreground" />
                    </button>
                    {openDocuments.length > 0 && (
                        <button
                            onClick={closeAllDocuments}
                            className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-black/5 dark:hover:bg-white/5 text-[9px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-all border border-border/50"
                        >
                            <X className="w-2.5 h-2.5" />
                        </button>
                    )}
                </div>
            </div>

            {/* Monaco Instance or Specialized Viewer */}
            <div className="flex-1 w-full h-full overflow-hidden relative">
                {activeDoc.content === undefined && !['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'pdf'].includes(activeDoc.type.toLowerCase()) ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-transparent z-10 gap-3">
                        <Loader2 className="w-8 h-8 animate-spin text-primary" />
                        <span className="text-[10px] uppercase tracking-widest text-muted-foreground animate-pulse">Loading Content...</span>
                    </div>
                ) : (
                    (() => {
                        const ext = activeDoc.type.toLowerCase();

                        // IMAGE VIEWER
                        if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) {
                            // In Electron, we can use the local file path as src if we have a protocol or just file:// if allowed
                            // However, since we are using a dev server, we should probably use the base64 or a direct link if accessible
                            return (
                                <div className="h-full w-full flex items-center justify-center p-8 bg-zinc-950/20">
                                    <img
                                        src={`file://${activeDoc.id}`}
                                        alt={activeDoc.title}
                                        className="max-w-full max-h-full object-contain shadow-2xl rounded-sm transition-transform hover:scale-[1.02]"
                                        onError={(e) => {
                                            (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400?text=Error+Loading+Image';
                                        }}
                                    />
                                </div>
                            );
                        }

                        // PDF VIEWER
                        if (ext === 'pdf') {
                            return (
                                <div className="h-full w-full flex flex-col items-center justify-center bg-zinc-900/40 p-12">
                                    <div className="p-10 rounded-3xl bg-card/40 border border-white/5 backdrop-blur-xl flex flex-col items-center gap-6 shadow-2xl">
                                        <div className="w-20 h-20 rounded-2xl bg-red-500/10 flex items-center justify-center border border-red-500/20">
                                            <FileText className="w-10 h-10 text-red-400" />
                                        </div>
                                        <div className="text-center space-y-2">
                                            <h3 className="text-xl font-bold bg-gradient-to-br from-white to-white/50 bg-clip-text text-transparent italic">PDF Document</h3>
                                            <p className="text-sm text-muted-foreground max-w-[250px]">{activeDoc.title}</p>
                                        </div>
                                        <Button
                                            onClick={() => window.electronAPI.send('shell:reveal', activeDoc.id)}
                                            variant="secondary"
                                            className="bg-white/5 hover:bg-white/10 border-white/10"
                                        >
                                            <ExternalLink className="w-4 h-4 mr-2" />
                                            Open with System Viewer
                                        </Button>
                                    </div>
                                </div>
                            );
                        }

                        // BINARY SAFEGUARD (Massive files or known destructive binary extensions)
                        // We set limit to 100MB (100 * 1024 * 1024)
                        const binaryExts = ['zip', 'exe', 'dll', 'so', 'dylib', 'woff', 'woff2', 'ttf', 'bin'];
                        const isMassive = activeDoc.content && activeDoc.content.length > 100 * 1024 * 1024;

                        if (binaryExts.includes(ext) || isMassive) {
                            return (
                                <div className="h-full w-full flex flex-col items-center justify-center bg-zinc-900/40 p-12">
                                    <div className="p-10 rounded-3xl bg-card/40 border border-white/5 backdrop-blur-xl flex flex-col items-center gap-6 shadow-2xl">
                                        <div className="w-20 h-20 rounded-2xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                                            <FileCode className="w-10 h-10 text-amber-400" />
                                        </div>
                                        <div className="text-center space-y-2">
                                            <h3 className="text-xl font-bold bg-gradient-to-br from-white to-white/50 bg-clip-text text-transparent italic text-amber-500">
                                                {isMassive ? 'Massive File' : 'Binary File'}
                                            </h3>
                                            <p className="text-sm text-muted-foreground">
                                                {isMassive ? 'This file is too large (>100MB) to open safely in the IDE.' : 'This file format is binary and cannot be edited as text.'}
                                            </p>
                                        </div>
                                        <Button
                                            onClick={() => window.electronAPI.send('shell:reveal', activeDoc.id)}
                                            variant="secondary"
                                            className="bg-white/5 hover:bg-white/10 border-white/10"
                                        >
                                            <ExternalLink className="w-4 h-4 mr-2" />
                                            Reveal in Finder
                                        </Button>
                                    </div>
                                </div>
                            );
                        }

                        if (activeDoc.type === 'git_diff') {
                            const filename = activeDoc.id.split(':').pop() || '';
                            return (
                                <DiffEditor
                                    height="100%"
                                    original={activeDoc.originalContent || ''}
                                    modified={activeDoc.modifiedContent || ''}
                                    language={getLanguage(filename.split('.').pop() || '')}
                                    theme={theme === 'dark' ? 'arcturus-dark' : 'arcturus-light'}
                                    onMount={handleEditorDidMount}
                                    options={{
                                        renderSideBySide: true,
                                        readOnly: true,
                                        originalEditable: false,
                                        fontSize: 13,
                                        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                                        padding: { top: 16 },
                                        scrollBeyondLastLine: false,
                                        automaticLayout: true,
                                        ignoreTrimWhitespace: false,
                                    }}
                                />
                            );
                        }

                        // DEFAULT MONACO
                        return (
                            <Editor
                                height="100%"
                                path={activeDoc.id} // Important for Monaco models
                                language={getLanguage(activeDoc.type)}
                                value={activeDoc.content || ''}
                                onChange={(value) => updateDocumentContent(activeDoc.id, value || '')}
                                onMount={handleEditorDidMount}
                                theme={theme === 'dark' ? 'arcturus-dark' : 'arcturus-light'}
                                options={{
                                    minimap: { enabled: true },
                                    fontSize: 13,
                                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                                    padding: { top: 16 },
                                    scrollBeyondLastLine: false,
                                    automaticLayout: true,
                                    smoothScrolling: true,
                                    cursorBlinking: "smooth",
                                    cursorSmoothCaretAnimation: "on",
                                    renderLineHighlight: 'all',
                                }}
                            />
                        );
                    })()
                )}
            </div>
        </div>
    );
};
