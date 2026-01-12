import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { marked } from 'marked';
import TurndownService from 'turndown';
import { useAppStore } from '@/store';
import { Button } from "@/components/ui/button";
import { Loader2, Edit2, Eye, FileText, Code2, Type, Minus, Plus, Maximize2, Minimize2 } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Initialize Turndown service
const turndownService = new TurndownService({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced'
});

export const NotesEditor: React.FC = () => {
    const { activeDocumentId, openDocuments, isZenMode, toggleZenMode } = useAppStore();
    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);

    // States
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [lastSavedContent, setLastSavedContent] = useState("");
    const [mode, setMode] = useState<'wysiwyg' | 'raw'>('wysiwyg');
    const [rawContent, setRawContent] = useState("");
    const [fontSize, setFontSize] = useState(16);

    const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const isFetchingRef = useRef(false);

    // Setup TipTap
    const editor = useEditor({
        extensions: [
            StarterKit,
            Placeholder.configure({
                placeholder: 'Start writing... (Type # for heading, * for list)',
            }),
        ],
        editorProps: {
            attributes: {
                class: 'prose dark:prose-invert prose-blue max-w-none focus:outline-none min-h-[200px] px-8 py-6 text-foreground',
            },
        },
        onUpdate: ({ editor }) => {
            // On editor usage, convert to MD and modify rawContent (which triggers autosave logic)
            const html = editor.getHTML();
            const md = turndownService.turndown(html);
            setRawContent(md);
        }
    });

    // Fetch Content
    useEffect(() => {
        if (!activeDocumentId) return;

        const fetchContent = async () => {
            setIsLoading(true);
            isFetchingRef.current = true;
            try {
                const res = await axios.get(`${API_BASE}/rag/document_content`, {
                    params: { path: activeDocumentId }
                });
                if (res.data.content !== undefined) {
                    const content = res.data.content;
                    setRawContent(content);
                    setLastSavedContent(content);

                    // Update Editor Content if in WYSIWYG mode
                    if (editor) {
                        try {
                            const html = await marked.parse(content);
                            editor.commands.setContent(html);
                        } catch (e) {
                            console.error("Markdown parsing failed", e);
                        }
                    }
                }
            } catch (e) {
                console.error("Failed to load note content", e);
            } finally {
                setIsLoading(false);
                // add a small delay to prevent auto-save from triggering immediately due to setRawContent
                setTimeout(() => { isFetchingRef.current = false; }, 500);
            }
        };
        fetchContent();
    }, [activeDocumentId, editor]); // Dependent on editor existence to set initial content

    // Save Logic
    const saveContent = useCallback(async (textToSave: string) => {
        if (!activeDocumentId) return;
        setIsSaving(true);
        try {
            const formData = new FormData();
            formData.append("path", activeDocumentId);
            formData.append("content", textToSave);

            await axios.post(`${API_BASE}/rag/save_file`, formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            setLastSavedContent(textToSave);
        } catch (e) {
            console.error("Failed to save note", e);
        } finally {
            setIsSaving(false);
        }
    }, [activeDocumentId]);

    // Auto-save
    useEffect(() => {
        if (isFetchingRef.current) return; // Don't save if we just loaded
        if (rawContent !== lastSavedContent && !isLoading) {
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
            saveTimeoutRef.current = setTimeout(() => {
                saveContent(rawContent);
            }, 1000);
        }
    }, [rawContent, lastSavedContent, isLoading, saveContent]);

    // Manual Save
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 's') {
                e.preventDefault();
                saveContent(rawContent);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [rawContent, saveContent]);

    // Handle Mode Switch
    const toggleMode = async () => {
        if (mode === 'wysiwyg') {
            // Switching to Raw: rawContent is already up to date via onUpdate
            setMode('raw');
        } else {
            // Switching to WYSIWYG: update editor with current rawContent
            if (editor) {
                const html = await marked.parse(rawContent);
                editor.commands.setContent(html);
            }
            setMode('wysiwyg');
        }
    };

    if (!activeDocumentId) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground/50">
                <FileText className="w-16 h-16 opacity-10 mb-4" />
                <p className="text-lg font-medium">Select a note to edit</p>
            </div>
        );
    }

    if (isLoading && !editor) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-background/50 backdrop-blur-sm">
            {/* Toolbar */}
            <div className="flex items-center justify-between p-3 border-b border-border/50 bg-muted/20">
                <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-foreground/80 truncate max-w-[300px]">
                        {activeDoc?.title || activeDocumentId.split('/').pop()}
                    </span>
                    {isSaving && <span className="text-xs text-muted-foreground animate-pulse">Saving...</span>}
                    {!isSaving && rawContent !== lastSavedContent && <span className="text-xs text-yellow-500">Unsaved changes</span>}
                </div>

                <div className="flex items-center gap-1 bg-muted/90 p-1 rounded-sm">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-foreground mr-1"
                        onClick={toggleZenMode}
                        title={isZenMode ? "Exit Full Width" : "Full Width"}
                    >
                        {isZenMode ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                    </Button>
                    <div className="flex items-center border-r border-border/50 pr-1 mr-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            onClick={() => setFontSize(s => Math.max(12, s - 1))}
                        >
                            <Minus className="w-3 h-3" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            onClick={() => setFontSize(s => Math.min(32, s + 1))}
                        >
                            <Plus className="w-3 h-3" />
                        </Button>
                    </div>
                    <Button
                        variant="ghost"
                        onClick={toggleMode}
                        className={cn("h-7 px-3 text-xs gap-2", "text-muted-foreground hover:text-foreground")}
                    >
                        {mode === 'wysiwyg' ? <Code2 className="w-2 h-2" /> : <Type className="w-2 h-2" />}
                        {/* {mode === 'wysiwyg' ? "Raw Source" : "Visual Editor"} */}
                    </Button>
                </div>
            </div>

            {/* Editor Area */}
            <div className="flex-1 overflow-auto relative" style={{ fontSize: `${fontSize}px` }}>
                {mode === 'raw' ? (
                    <textarea
                        className="w-full h-full p-8 resize-none bg-transparent outline-none font-mono leading-relaxed text-foreground"
                        value={rawContent}
                        style={{ fontSize: `${fontSize}px` }}
                        onChange={(e) => setContentRaw(e.target.value)}
                        placeholder="# Start writing your note..."
                    />
                ) : (
                    <div
                        className="h-full prose dark:prose-invert prose-blue max-w-none"
                        style={{ fontSize: `${fontSize}px` }}
                    >
                        <style>{`
                            .tiptap-editor-container .tiptap {
                                font-size: inherit !important;
                                line-height: 1.6;
                            }
                            .tiptap-editor-container .prose p, 
                            .tiptap-editor-container .prose li,
                            .tiptap-editor-container .prose h1,
                            .tiptap-editor-container .prose h2,
                            .tiptap-editor-container .prose h3 {
                                font-size: inherit !important;
                            }
                        `}</style>
                        <div className="tiptap-editor-container h-full">
                            <EditorContent editor={editor} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );

    // Helper to update raw content and sync if needed
    function setContentRaw(val: string) {
        setRawContent(val);
        // If in raw mode, we don't update editor immediately to avoid cursor jumping, 
        // we update editor only when switching back
    }
};
