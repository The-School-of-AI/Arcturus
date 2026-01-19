import React, { useEffect, useState, useCallback, useRef } from 'react';
import Editor, { loader, DiffEditor } from '@monaco-editor/react';
import { useAppStore } from '@/store';
import { useIdeStore } from '../store/ideStore';
import { FileCode, Loader2, X, FileText, Code2, ExternalLink, Save, CheckCircle2 } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/components/theme';
import { Button } from '@/components/ui/button';
import { SelectionMenu } from '@/components/common/SelectionMenu';

// Configure Monaco to use local resources if needed, or just standard setup
loader.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs' } });

export const EditorArea: React.FC = () => {
    const {
        ideOpenDocuments,
        ideActiveDocumentId,
        updateIdeDocumentContent,
        markIdeDocumentSaved,
        setActiveIdeDocument,
        closeIdeDocument,
        closeAllIdeDocuments,
        addSelectedContext,
        reviewRequest,
        submitReviewDecision
    } = useAppStore();

    // Arcturus Timer Hook
    const { resetArcturusTimer, startArcturusTimer, arcturusTimer } = useIdeStore();

    const { theme } = useTheme();
    const [isSaving, setIsSaving] = useState(false);
    const [lastSaved, setLastSaved] = useState<string | null>(null);
    const [selectionMenu, setSelectionMenu] = useState<{
        visible: boolean,
        x: number,
        y: number,
        text: string,
        metadata?: { file: string, range: { startLine: number, endLine: number } }
    }>({ visible: false, x: 0, y: 0, text: '' });

    const editorRef = useRef<any>(null);
    const monacoRef = useRef<any>(null);
    const { explorerRootPath } = useAppStore();

    const activeDoc = ideOpenDocuments.find(d => d.id === ideActiveDocumentId);

    const handleEditorDidMount = (editor: any, monaco: any) => {
        editorRef.current = editor;
        monacoRef.current = monaco;

        editor.onDidChangeCursorSelection((e: any) => {
            const selection = editor.getSelection();
            const model = editor.getModel();
            if (!selection || !model) {
                setSelectionMenu(prev => ({ ...prev, visible: false }));
                return;
            }

            const text = model.getValueInRange(selection).trim();
            if (text.length > 0) {
                const endPos = selection.getEndPosition();
                const scrolledPos = editor.getScrolledVisiblePosition(endPos);
                const domNode = editor.getDomNode();

                if (scrolledPos && domNode) {
                    const rect = domNode.getBoundingClientRect();
                    const startLine = selection.startLineNumber;
                    const endLine = selection.endLineNumber;

                    setSelectionMenu({
                        visible: true,
                        x: rect.left + scrolledPos.left,
                        y: rect.top + scrolledPos.top - 40,
                        text,
                        metadata: {
                            file: activeDoc?.id || '',
                            range: { startLine, endLine }
                        }
                    });
                }
            } else {
                setSelectionMenu(prev => ({ ...prev, visible: false }));
            }
        });

        // Handle Initial Scroll if provided
        if ((activeDoc as any)?.initialLine) {
            setTimeout(() => {
                editor.revealLineInCenter((activeDoc as any).initialLine);
                editor.setPosition({ lineNumber: (activeDoc as any).initialLine, column: 1 });
            }, 100);
        }
    };

    // React to activeDoc changes for scrolling (e.g. clicking same file but different test)
    const decorationsRef = useRef<string[]>([]);

    useEffect(() => {
        if (editorRef.current && (activeDoc as any)?.initialLine && monacoRef.current) {
            const line = (activeDoc as any).initialLine;
            editorRef.current.revealLineInCenter(line);
            editorRef.current.setPosition({ lineNumber: line, column: 1 });

            // Apply strong highlight decoration
            const newDecorations = [
                {
                    range: new monacoRef.current.Range(line, 1, line, 1),
                    options: {
                        isWholeLine: true,
                        className: 'bg-green-500/20 border-l-4 border-green-600', // Git diff style
                    }
                }
            ];

            decorationsRef.current = editorRef.current.deltaDecorations(decorationsRef.current, newDecorations);
        }
    }, [activeDoc?.id, (activeDoc as any)?.initialLine]);

    const runLinting = useCallback(async (docId: string, content: string) => {
        if (!docId.endsWith('.py') || !explorerRootPath || !monacoRef.current || !editorRef.current) return;

        const relPath = docId.replace(explorerRootPath, '').replace(/^\//, '');

        try {
            // 1. Lint (Ruff)
            const res = await axios.post(`${API_BASE}/python/lint`, {
                path: explorerRootPath,
                file_path: relPath
            });

            if (res.data.success) {
                const diagnostics = res.data.diagnostics || [];
                const markers = diagnostics.map((d: any) => ({
                    startLineNumber: d.location.row,
                    startColumn: d.location.column,
                    endLineNumber: d.end_location.row,
                    endColumn: d.end_location.column,
                    message: `[Ruff] ${d.message} (${d.code})`,
                    severity: monacoRef.current.MarkerSeverity.Warning
                }));

                const model = editorRef.current.getModel();
                if (model) { // Ensure model matches? Usually editorRef points to current
                    monacoRef.current.editor.setModelMarkers(model, 'ruff', markers);
                }
            }
        } catch (e) {
            console.error("[Lint] Failed:", e);
        }
    }, [explorerRootPath]);

    // Initial Lint on Reference/Doc Change
    useEffect(() => {
        if (activeDoc?.content && activeDoc.id.endsWith('.py')) {
            // Small delay to ensure editor model is ready
            const timer = setTimeout(() => {
                runLinting(activeDoc.id, activeDoc.content!);
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [activeDoc?.id, activeDoc?.content, runLinting]);


    const handleSave = useCallback(async () => {
        if (!activeDoc || activeDoc.content === undefined) return;

        setIsSaving(true);
        try {
            let contentToSave = activeDoc.content;

            // Python Formatting
            if (activeDoc.id.endsWith('.py') && explorerRootPath) {
                try {
                    const res = await axios.post(`${API_BASE}/python/format`, {
                        path: explorerRootPath,
                        file_path: activeDoc.id.replace(explorerRootPath, '').replace(/^\//, ''),
                        content: contentToSave
                    }, { timeout: 2000 }); // 2s timeout to prevent blocking save
                    if (res.data.success && res.data.formatted_content) {
                        contentToSave = res.data.formatted_content;
                        // Update editor content immediately if changed
                        if (contentToSave !== activeDoc.content) {
                            updateIdeDocumentContent(activeDoc.id, contentToSave, true);
                        }
                    }
                } catch (e) {
                    console.error("Format failed", e);
                }
            }

            const result = await window.electronAPI.invoke('fs:writeFile', {
                path: activeDoc.id,
                content: contentToSave
            });

            if (result && result.success) {
                markIdeDocumentSaved(activeDoc.id);
                setLastSaved(activeDoc.id);
                setTimeout(() => setLastSaved(null), 2000);

                // Trigger Arcturus Timer (Start or Reset)
                if (arcturusTimer.countdown === null) {
                    startArcturusTimer();
                } else {
                    resetArcturusTimer();
                }

                // Run Linting & Type Checking (Python)
                await runLinting(activeDoc.id, contentToSave);
            } else {
                console.error("Save operation returned failure:", result);
                // Alert the user
                await window.electronAPI.invoke('dialog:alert', {
                    title: "Save Failed",
                    message: `Could not save file: ${result?.error || 'Unknown error'}`
                });
            }
        } catch (error) {
            console.error('Failed to save file:', error);
        } finally {
            setIsSaving(false);
        }
    }, [activeDoc, activeDoc?.id, activeDoc?.content, explorerRootPath, arcturusTimer.countdown, startArcturusTimer, resetArcturusTimer, markIdeDocumentSaved, updateIdeDocumentContent, runLinting]);

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

        // Skip fetching for folders or known binary types that we render differently
        const binaryTypes = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf', 'ico', 'mp4', 'webm'];
        if (activeDoc.type === 'folder' || binaryTypes.includes(activeDoc.type.toLowerCase())) return;

        if (activeDoc.content === undefined) {
            const fetchContent = async () => {
                try {
                    // Use Electron IPC to read file directly
                    const result = await window.electronAPI.invoke('fs:readFile', activeDoc.id);

                    if (result && result.success) {
                        updateIdeDocumentContent(activeDoc.id, result.content, false);
                    } else {
                        throw new Error(result?.error || 'Unknown error');
                    }
                } catch (e: any) {
                    console.error("Failed to load document content", e);
                    updateIdeDocumentContent(activeDoc.id, `// Failed to load content.\n// Error: ${e.message || e}\n// The file might be binary or inaccessible.`, false);
                }
            };
            fetchContent();
        }
    }, [activeDoc?.id, activeDoc?.content]);

    // Custom Monaco Theme to match RAG/App Theme
    const handleBeforeMount = (monaco: any) => {
        // Dark Theme
        monaco.editor.defineTheme('arcturus-dark', {
            base: 'vs-dark',
            inherit: true,
            rules: [
                { token: 'comment', foreground: '6B7A90' },
                { token: 'keyword', foreground: '569CD6' },
                { token: 'string', foreground: 'CE9178' },
                { token: 'number', foreground: 'B5CEA8' },
                { token: 'type', foreground: '4EC9B0' },
                { token: 'function', foreground: 'DCDCAA' },
            ],
            colors: {
                'editor.background': '#00000000', // Transparent
                'editor.lineHighlightBackground': '#ffffff0a',
                'editorLineNumber.foreground': '#4b5563',
                'editor.selectionBackground': '#264f78',
                'editor.inactiveSelectionBackground': '#3a3d41',
                'editor.findMatchHighlightBackground': '#4588F11F',
                'editor.findRangeHighlightBackground': '#4588F114',
                'editorWidget.background': '#0B1220',
                'editorWidget.border': '#1F304F',
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
                'editor.background': '#00000000',
                'editor.lineHighlightBackground': '#0000000a',
                'editorLineNumber.foreground': '#a1a1aa',
                'editor.selectionBackground': '#add6ff',
                'editor.inactiveSelectionBackground': '#e5e7eb',
            }
        });
    };

    const getLanguage = (ext: string) => {
        const mapping: Record<string, string> = {
            'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
            'py': 'python', 'json': 'json', 'yaml': 'yaml', 'yml': 'yaml', 'html': 'html',
            'css': 'css', 'scss': 'scss', 'md': 'markdown', 'sh': 'shell', 'sql': 'sql'
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
        <div className={cn("h-full flex flex-col border-t transition-colors", theme === 'dark' ? "bg-transparent border-border/50" : "bg-white/80 border-border")}>
            {/* Tab Bar */}
            <div className="flex items-center justify-between border-b border-border bg-muted/30 pr-4 shrink-0 h-10">
                <div className="flex items-center gap-[1px] px-2 h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {ideOpenDocuments.map(doc => (
                        <div
                            key={doc.id}
                            onClick={() => setActiveIdeDocument(doc.id)}
                            className={cn(
                                "group flex items-center gap-1.5 px-3 h-9 mt-auto rounded-t-lg transition-all cursor-pointer min-w-[100px] max-w-[200px] border-x border-t border-transparent relative select-none",
                                ideActiveDocumentId === doc.id
                                    ? (theme === 'dark' ? "bg-background border-border text-foreground z-10 font-bold" : "bg-white border-border text-foreground z-10")
                                    : "bg-muted/50 text-muted-foreground hover:bg-muted"
                            )}
                        >
                            <FileCode className="w-3.5 h-3.5 shrink-0 text-blue-400" />
                            <span className="text-[11px] font-medium truncate flex-1">{doc.title}</span>
                            {doc.isDirty && <div className="w-2 h-2 rounded-full bg-orange-500 shrink-0 mr-1" />}
                            <button onClick={(e) => { e.stopPropagation(); closeIdeDocument(doc.id); }} className="p-0.5 rounded-md hover:bg-black/5 dark:hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity">
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    ))}
                </div>
                <div className="flex items-center gap-2">
                    {lastSaved === ideActiveDocumentId && (
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-green-500/10 text-green-500 text-[10px] font-medium">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Saved</span>
                        </div>
                    )}
                    <button onClick={handleSave} disabled={isSaving || !activeDoc} className="p-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50">
                        <Save className="w-4 h-4 text-muted-foreground" />
                    </button>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 w-full h-full overflow-hidden relative">
                {activeDoc.content === undefined && !['pdf', 'png', 'jpg', 'jpeg', 'gif', 'svg'].includes(activeDoc.type.toLowerCase()) ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-transparent z-10 gap-3">
                        <Loader2 className="w-8 h-8 animate-spin text-primary" />
                    </div>
                ) : (
                    (() => {
                        const ext = activeDoc.type.toLowerCase();
                        if (['png', 'jpg', 'jpeg', 'gif', 'svg'].includes(ext)) {
                            return <div className="h-full w-full flex items-center justify-center p-8"><img src={`file://${activeDoc.id}`} className="max-w-full max-h-full object-contain" /></div>;
                        }

                        // Debug language detection
                        const detectedLang = activeDoc.language || getLanguage(activeDoc.id.split('.').pop() || activeDoc.type);

                        if (ext === 'pdf') {
                            return <div className="h-full w-full flex flex-col items-center justify-center bg-zinc-900/40 p-12"><FileText className="w-12 h-12 text-red-400" /></div>;
                        }
                        if (activeDoc.type === 'git_diff') {
                            const filename = activeDoc.id.split(':').pop() || '';
                            return <DiffEditor height="100%" original={activeDoc.originalContent || ''} modified={activeDoc.modifiedContent || ''} language={getLanguage(filename.split('.').pop() || '')} theme={theme === 'dark' ? 'arcturus-dark' : 'arcturus-light'} beforeMount={handleBeforeMount} options={{ fontSize: 13, automaticLayout: true, renderSideBySide: false }} />;
                        }
                        return <Editor
                            height="100%"
                            path={activeDoc.id}
                            language={activeDoc.language || getLanguage(activeDoc.id.split('.').pop() || activeDoc.type)}
                            value={activeDoc.content || ''}
                            onChange={(val) => updateIdeDocumentContent(activeDoc.id, val || '', true)}
                            beforeMount={handleBeforeMount}
                            onMount={handleEditorDidMount}
                            theme={theme === 'dark' ? 'arcturus-dark' : 'arcturus-light'}
                            options={{ fontSize: 13, automaticLayout: true, minimap: { enabled: false } }}
                        />;
                    })()
                )}
                {/* Global Selection Menu for IDE */}
                <SelectionMenu
                    onAdd={(text) => {
                        if (selectionMenu.metadata) {
                            addSelectedContext({
                                id: crypto.randomUUID(),
                                text: text,
                                file: selectionMenu.metadata.file,
                                range: selectionMenu.metadata.range
                            });
                        } else {
                            addSelectedContext(text);
                        }
                        setSelectionMenu(prev => ({ ...prev, visible: false }));
                    }}
                    manualVisible={selectionMenu.visible}
                    manualPosition={{ x: selectionMenu.x, y: selectionMenu.y }}
                    manualText={selectionMenu.text}
                />

                {/* Inline Review Controls */}
                {activeDoc.type === 'git_diff' && reviewRequest && activeDoc.id.includes(reviewRequest.path || '') && (
                    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center justify-between gap-4 px-4 py-2 bg-[#1e1e1e] border border-[#3e3e3e] shadow-2xl rounded-full animate-in slide-in-from-bottom-2 fade-in duration-300 min-w-[300px]">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                            <span className="text-xs font-medium text-gray-300">
                                {reviewRequest.operation || "Review Changes"}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-3 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/30 rounded-full"
                                onClick={() => submitReviewDecision('deny')}
                            >
                                Reject
                            </Button>
                            <Button
                                size="sm"
                                className="h-7 px-4 text-xs bg-blue-600 hover:bg-blue-500 text-white border-0 rounded-full shadow-lg shadow-blue-900/20"
                                onClick={() => submitReviewDecision('allow_once')}
                            >
                                Accept Changes
                            </Button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
