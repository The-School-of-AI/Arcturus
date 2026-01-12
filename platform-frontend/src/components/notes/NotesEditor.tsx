import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Image from '@tiptap/extension-image';
import { marked } from 'marked';
import TurndownService from 'turndown';
import { useAppStore } from '@/store';
import { Button } from "@/components/ui/button";
import { Loader2, Edit2, Eye, FileText, Code2, Type, Minus, Plus, Maximize2, Minimize2, X } from 'lucide-react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import Mention from '@tiptap/extension-mention';
import tippy from 'tippy.js';
import type { Instance as TippyInstance } from 'tippy.js';
import { ReactRenderer } from '@tiptap/react';
import { WikiLinkList } from './WikiLinkList';

// Initialize Turndown service
const turndownService = new TurndownService({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced'
});

// CRITICAL: Disable Turndown's aggressive escaping to prevent '[[link]] \]' bugs
// This ensures that our markdown notes remain clean and Obsidian-compatible.
turndownService.escape = (text: string) => text;

// Rule to convert resolved API URLs back to relative paths for storage
turndownService.addRule('unresolveImages', {
    filter: 'img',
    replacement: function (content, node: any) {
        const src = node.getAttribute('src');
        const alt = node.getAttribute('alt') || '';
        let markdownAlt = alt;

        // Extract width/scale and alignment from style to restore Obsidian syntax
        const style = node.getAttribute('style') || '';
        const flags: string[] = [];

        // 1. Position/Float flags
        if (style.includes('float: left')) flags.push('float-l');
        else if (style.includes('float: right')) flags.push('float-r');
        else if (style.includes('margin-left: 0') && style.includes('margin-right: auto')) flags.push('left');
        else if (style.includes('margin-left: auto') && style.includes('margin-right: 0')) flags.push('right');
        else if (style.includes('margin-left: auto') && style.includes('margin-right: auto')) flags.push('center');

        // 2. Size flag
        const widthMatch = style.match(/width:\s*([^;]+)/);
        if (widthMatch) {
            let widthValue = widthMatch[1].trim();
            if (widthValue.endsWith('%')) {
                const percent = parseInt(widthValue);
                widthValue = (percent / 100).toString();
            } else if (widthValue.endsWith('px')) {
                widthValue = widthValue.replace('px', '');
            }
            flags.push(widthValue);
        }

        if (flags.length > 0) {
            // Reconstruct the pipe syntax: ![Alt|flag1|flag2]
            const baseAlt = alt.includes('|') ? alt.split('|')[0] : alt;
            markdownAlt = (baseAlt ? baseAlt : '') + '|' + flags.join('|');
        }

        if (src && src.includes('/rag/document_content?path=')) {
            try {
                const url = new URL(src);
                const fullPath = url.searchParams.get('path');
                if (fullPath) {
                    const parts = fullPath.split('/');
                    const filename = parts.pop();
                    const subfolder = parts.pop();
                    if (subfolder === 'attachments') {
                        return `![${markdownAlt}](./attachments/${filename})`;
                    }
                }
            } catch (e) {
                console.error("Failed to unresolve image URL", e);
            }
        }
        return `![${markdownAlt}](${src})`;
    }
});

// WikiLink rule for Turndown
turndownService.addRule('wikilinks', {
    filter: (node) => node.nodeName === 'A' && node.getAttribute('data-type') === 'wikilink',
    replacement: (content, node: any) => {
        const path = node.getAttribute('data-id');
        const alias = node.textContent;
        const noteName = path.split('/').pop()?.replace('.md', '');
        if (alias && alias !== noteName) {
            return `[[${path}|${alias}]]`;
        }
        return `[[${path}]]`;
    }
});

// Move the image rule after... (wait, actually I should keep it organized)

// Extend TipTap Image to support scaling via style attribute
const ScaledImage = Image.extend({
    addAttributes() {
        return {
            ...this.parent?.(),
            style: {
                default: null,
                parseHTML: (element: HTMLElement) => element.getAttribute('style'),
                renderHTML: (attributes: any) => {
                    if (!attributes.style) return {};
                    return { style: attributes.style };
                },
            },
        };
    },
});

// Custom WikiLink Extension
const WikiLink = Mention.extend({
    name: 'wikilink',
    addAttributes() {
        return {
            id: {
                default: null,
                parseHTML: element => element.getAttribute('data-id'),
                renderHTML: attributes => {
                    if (!attributes.id) return {};
                    return { 'data-id': attributes.id };
                },
            },
            label: {
                default: null,
                parseHTML: element => element.getAttribute('data-label'),
                renderHTML: attributes => {
                    if (!attributes.label) return {};
                    return { 'data-label': attributes.label };
                },
            },
            targetLine: {
                default: null,
                parseHTML: element => element.getAttribute('data-line'),
                renderHTML: attributes => {
                    if (!attributes.targetLine) return {};
                    return { 'data-line': attributes.targetLine };
                },
            },
            searchText: {
                default: null,
                parseHTML: element => element.getAttribute('data-search'),
                renderHTML: attributes => {
                    if (!attributes.searchText) return {};
                    return { 'data-search': attributes.searchText };
                },
            }
        };
    },
    renderHTML({ node, HTMLAttributes }) {
        return ['a', {
            ...HTMLAttributes,
            'data-type': 'wikilink',
            class: 'text-blue-500 hover:underline cursor-pointer font-medium decoration-blue-500/30'
        }, node.attrs.label || node.attrs.id];
    },
    renderText({ node }) {
        return `[[${node.attrs.label || node.attrs.id}]]`;
    },
    parseHTML() {
        return [
            {
                tag: 'a[data-type="wikilink"]',
                getAttrs: element => {
                    if (typeof element === 'string') return false;
                    return {
                        id: element.getAttribute('data-id'),
                        label: element.textContent,
                        targetLine: element.getAttribute('data-line'),
                        searchText: element.getAttribute('data-search'),
                    };
                },
            },
        ];
    },
});

export const NotesEditor: React.FC = () => {
    const {
        activeDocumentId,
        openDocuments,
        setActiveDocument,
        openDocument,
        closeDocument,
        closeAllDocuments,
        isZenMode,
        toggleZenMode
    } = useAppStore();
    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);

    // States
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [lastSavedContent, setLastSavedContent] = useState("");
    const [mode, setMode] = useState<'wysiwyg' | 'raw'>('wysiwyg');
    const [rawContent, setRawContent] = useState("");
    const [fontSize, setFontSize] = useState(16);

    // Derived state for comparison
    const trimmedCurrent = rawContent.trim();
    const trimmedLast = lastSavedContent.trim();

    const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const isFetchingRef = useRef(false);

    // Setup TipTap
    // Suggestion logic
    const [allNotes, setAllNotes] = useState<string[]>([]);

    useEffect(() => {
        const fetchAllNotes = async () => {
            try {
                const res = await axios.get(`${API_BASE}/rag/documents`);
                const extractMdFiles = (items: any[]): string[] => {
                    let result: string[] = [];
                    items.forEach(item => {
                        if (item.type === 'md' || item.type === 'markdown') {
                            result.push(item.path);
                        }
                        if (item.children) {
                            result = [...result, ...extractMdFiles(item.children)];
                        }
                    });
                    return result;
                };
                if (res.data.files) {
                    setAllNotes(extractMdFiles(res.data.files));
                }
            } catch (e) {
                console.error("Failed to fetch notes for suggestions", e);
            }
        };
        fetchAllNotes();
    }, [activeDocumentId]);

    const handleWikiLinkClick = useCallback(async (path: string, targetLine?: number, searchText?: string) => {
        if (!path) return;

        // If it's a web URL, open it in a new tab
        if (path.startsWith('http') || (path.includes('.') && !path.includes('/') && !path.endsWith('.md'))) {
            let url = path;
            if (!url.startsWith('http')) url = 'https://' + url;
            window.open(url, '_blank');
            return;
        }

        // If path doesn't end with .md, add it
        const fullPath = path.endsWith('.md') ? path : `${path}.md`;

        // Navigate or Create
        try {
            // Check if file exists by trying to fetch its content
            await axios.get(`${API_BASE}/rag/document_content`, { params: { path: fullPath } });

            // Exists!
            openDocument({
                id: fullPath,
                title: fullPath.split('/').pop() || fullPath,
                type: 'note',
                targetLine: targetLine,
                searchText: searchText
            });
            setActiveDocument(fullPath);
        } catch (e) {
            // Doesn't exist, create it
            try {
                const formData = new FormData();
                formData.append("path", fullPath);
                formData.append("content", `# ${fullPath.split('/').pop()?.replace('.md', '')}\n\n`);
                await axios.post(`${API_BASE}/rag/save_file`, formData);

                openDocument({ id: fullPath, title: fullPath.split('/').pop() || fullPath, type: 'note' });
                setActiveDocument(fullPath);
            } catch (err) {
                console.error("Failed to create new note", err);
            }
        }
    }, [openDocument, setActiveDocument]);

    const suggestionConfig = {
        char: '[[',
        command: ({ editor, range, props }: any) => {
            if (!range) return;
            editor
                .chain()
                .focus()
                .insertContentAt(range, [
                    {
                        type: 'wikilink',
                        attrs: props,
                    },
                    {
                        type: 'text',
                        text: ' ',
                    },
                ])
                .run();
        },
        items: async ({ query }: { query: string }) => {
            if (!query || query.length < 2) {
                return allNotes
                    .filter(item => item.toLowerCase().includes(query.toLowerCase()))
                    .slice(0, 10);
            }

            try {
                const res = await axios.get(`${API_BASE}/rag/ripgrep_search`, {
                    params: {
                        query: query,
                        target_dir: "Notes"
                    }
                });

                const results = res.data?.results || [];
                // Group by file to avoid too many duplicate file entries if query is in many lines
                const seenFiles = new Set();
                const uniqueResults: any[] = [];

                results.forEach((r: any) => {
                    if (!seenFiles.has(r.file)) {
                        seenFiles.add(r.file);
                        uniqueResults.push(r);
                    }
                });

                // Mix with filename matches if not already in results
                const fileMatches = allNotes.filter(n =>
                    n.toLowerCase().includes(query.toLowerCase()) &&
                    !seenFiles.has(n) &&
                    !seenFiles.has(n.replace(/^Notes\//, ''))
                ).slice(0, 5);

                return [...uniqueResults, ...fileMatches].slice(0, 10);
            } catch (e) {
                console.error("WikiLink search failed", e);
                return allNotes
                    .filter(item => item.toLowerCase().includes(query.toLowerCase()))
                    .slice(0, 10);
            }
        },
        render: () => {
            let component: ReactRenderer<any>;
            let popup: TippyInstance[];

            return {
                onStart: (props: any) => {
                    component = new ReactRenderer(WikiLinkList, {
                        props,
                        editor: props.editor,
                    });

                    if (!props.clientRect) return;

                    popup = tippy('body', {
                        getReferenceClientRect: props.clientRect,
                        appendTo: () => document.body,
                        content: component.element,
                        showOnCreate: true,
                        interactive: true,
                        trigger: 'manual',
                        placement: 'bottom-start',
                    });
                },

                onUpdate(props: any) {
                    component.updateProps(props);

                    if (!props.clientRect) return;

                    if (popup && popup[0]) {
                        popup[0].setProps({
                            getReferenceClientRect: props.clientRect,
                        });
                    }
                },

                onKeyDown(props: any) {
                    if (props.event.key === 'Escape') {
                        if (popup && popup[0]) popup[0].hide();
                        return true;
                    }

                    return component.ref?.onKeyDown(props);
                },

                onExit() {
                    try {
                        if (popup && popup[0]) {
                            popup[0].hide();
                            popup[0].destroy();
                        }
                    } catch (e) {
                        console.warn("Error during suggestion cleanup", e);
                    }
                    component.destroy();
                },
            };
        },
    };

    const editor = useEditor({
        extensions: [
            StarterKit,
            ScaledImage.configure({
                HTMLAttributes: {
                    class: 'rounded-lg border border-border/50 max-w-full h-auto my-4 shadow-sm cursor-pointer hover:shadow-md transition-shadow',
                },
            }),
            WikiLink.configure({
                suggestion: suggestionConfig,
            }),
            Placeholder.configure({
                placeholder: 'Start writing... (Type # for heading, * for list, [[ for notes)',
            }),
        ],
        editorProps: {
            attributes: {
                class: 'prose dark:prose-invert prose-blue max-w-none focus:outline-none min-h-[200px] px-8 py-6 text-foreground',
            },
            handleClick: (view, pos, event) => {
                const node = view.state.doc.nodeAt(pos);
                if (node?.type.name === 'wikilink') {
                    handleWikiLinkClick(node.attrs.id, node.attrs.targetLine, node.attrs.searchText);
                    return true;
                }
                // Handle standard TipTap Link clicks too
                if (node?.type.name === 'text') {
                    const mark = node.marks.find(m => m.type.name === 'link');
                    if (mark) {
                        handleWikiLinkClick(mark.attrs.href);
                        return true;
                    }
                }
                return false;
            },
        },
        onUpdate: ({ editor }) => {
            // On editor usage, convert to MD and modify rawContent (which triggers autosave logic)
            const html = editor.getHTML();
            // Turndown preserves src as is by default
            const md = turndownService.turndown(html);
            setRawContent(md);
        }
    });

    // Helper to resolve relative image paths for rendering
    const resolveImagePath = useCallback((src: string) => {
        if (!activeDocumentId || !src) return src;
        if (src.startsWith('http') || src.startsWith('data:') || src.startsWith('blob:')) {
            return src;
        }

        // If it starts with ./ or is a simple relative path like 'attachments/...'
        let cleanSrc = src;
        if (src.startsWith('./')) {
            cleanSrc = src.substring(2);
        } else if (src.startsWith('/')) {
            // Absolute local paths won't render anyway, but we keep them so the backend can move them
            return src;
        }

        const parts = activeDocumentId.split('/');
        parts.pop(); // Remove filename
        const folder = parts.join('/');
        const fullPath = folder ? `${folder}/${cleanSrc}` : cleanSrc;
        return `${API_BASE}/rag/document_content?path=${encodeURIComponent(fullPath)}`;
    }, [activeDocumentId]);

    // Custom marked parser that resolves image paths
    // Custom marked parser that resolves image paths and handles scaling/alignment
    const handleParseMarkdown = useCallback(async (content: string) => {
        const renderer = new marked.Renderer();

        renderer.image = ({ href, title, text }: any) => {
            const resolvedSrc = resolveImagePath(href);
            let styles: string[] = [];
            let altText = text || '';

            // Obsidian-style scaling/alignment: ![alt|right|500](path)
            if (text && text.includes('|')) {
                const parts = text.split('|');
                altText = parts[0].trim();
                const flags = parts.slice(1).map((f: string) => f.trim().toLowerCase());

                flags.forEach((f: string) => {
                    if (!f) return;

                    // Alignment/Float Flags
                    if (f === 'left') {
                        styles.push('margin-left: 0', 'margin-right: auto', 'display: block');
                    } else if (f === 'right') {
                        styles.push('margin-left: auto', 'margin-right: 0', 'display: block');
                    } else if (f === 'center') {
                        styles.push('margin-left: auto', 'margin-right: auto', 'display: block');
                    } else if (f === 'float-l') {
                        styles.push('float: left', 'margin-right: 1.5rem', 'margin-bottom: 0.5rem');
                    } else if (f === 'float-r') {
                        styles.push('float: right', 'margin-left: 1.5rem', 'margin-bottom: 0.5rem');
                    }
                    // Size Flags
                    else if (f.includes('.') || (parseFloat(f) <= 1.0 && !f.includes('px'))) {
                        const ratio = parseFloat(f);
                        if (!isNaN(ratio)) styles.push(`width: ${ratio * 100}%`);
                    } else if (!isNaN(parseInt(f))) {
                        const px = parseInt(f);
                        if (!isNaN(px)) styles.push(`width: ${px}px`);
                    }
                });
            }

            // Default to display: block if no float to avoid weird inline issues
            if (!styles.some(s => s.includes('float') || s.includes('display'))) {
                styles.push('display: block', 'margin-left: auto', 'margin-right: auto');
            }

            const styleAttr = styles.length > 0 ? `style="${styles.join('; ')}"` : '';
            return `<img src="${resolvedSrc}" alt="${text || ''}" ${title ? `title="${title}"` : ''} ${styleAttr} />`;
        };
        // WikiLink rendering: [[Path]] or [[Path|Alias]]
        // Using a more precise regex to avoid capturing trailing artifacts
        const wikiLinkRegex = /\[\[([^\[\]]+?)\]\]/g;
        let finalContent = content.replace(wikiLinkRegex, (match, inner) => {
            const parts = inner.split('|');
            const path = parts[0].trim();
            const alias = parts[1] ? parts[1].trim() : path.split('/').pop()?.replace('.md', '');
            return `<a data-type="wikilink" data-id="${path}" class="text-blue-500 hover:underline cursor-pointer font-medium decoration-blue-500/30">${alias}</a>`;
        });

        return marked.parse(finalContent, { renderer });
    }, [resolveImagePath]);

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
                            const html = await handleParseMarkdown(content);
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

            const res = await axios.post(`${API_BASE}/rag/save_file`, formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });

            // If backend updated the content (e.g. moved images), sync it back
            if (res.data.content && res.data.content.trim() !== textToSave.trim()) {
                setRawContent(res.data.content);
                setLastSavedContent(res.data.content);

                // If in WYSIWYG mode, update editor without losing cursor if possible
                if (mode === 'wysiwyg' && editor) {
                    const html = await handleParseMarkdown(res.data.content);
                    const currentPos = editor.state.selection.from;
                    editor.commands.setContent(html, { emitUpdate: false });
                    try {
                        editor.commands.setTextSelection(currentPos);
                    } catch (e) {
                        // Position might be out of range if content shortened significantly
                    }
                }
            } else {
                setLastSavedContent(textToSave);
            }
        } catch (e) {
            console.error("Failed to save note", e);
        } finally {
            setIsSaving(false);
        }
    }, [activeDocumentId]);

    // Auto-save logic
    useEffect(() => {
        if (isFetchingRef.current || isLoading) return;

        // Trim for comparison to avoid whitespace issues triggering unnecessary saves
        const trimmedCurrent = rawContent.trim();
        const trimmedLast = lastSavedContent.trim();

        if (trimmedCurrent !== trimmedLast && trimmedCurrent.length > 0) {
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
            saveTimeoutRef.current = setTimeout(() => {
                saveContent(rawContent);
            }, 1500); // 1.5s delay for auto-save
        }
    }, [rawContent, lastSavedContent, isLoading, saveContent]);

    // Cleanup timeout on unmount
    useEffect(() => {
        return () => {
            if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
        };
    }, []);

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
        // Save current content before switching to ensure NO loss
        await saveContent(rawContent);

        if (mode === 'wysiwyg') {
            setMode('raw');
        } else {
            // Switching to WYSIWYG: update editor with current rawContent
            if (editor) {
                const html = await handleParseMarkdown(rawContent);
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
            {/* Tab Bar - Browser Style */}
            <div className="flex items-center justify-between border-b border-border bg-muted/30 pr-4 shrink-0 h-10">
                <div className="flex items-center gap-[1px] px-2 h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {openDocuments.map(doc => {
                        const isNote = doc.type === 'note' || doc.id.endsWith('.md');
                        return (
                            <div
                                key={doc.id}
                                onClick={() => setActiveDocument(doc.id)}
                                className={cn(
                                    "group flex items-center gap-1.5 px-3 h-8 mt-auto rounded-t-lg transition-all cursor-pointer min-w-[80px] max-w-[180px] border-x border-t border-transparent relative",
                                    activeDocumentId === doc.id
                                        ? "bg-background border-border text-foreground z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-background shadow-[0_-4px_12px_rgba(0,0,0,0.1)]"
                                        : "bg-muted/10 text-muted-foreground hover:bg-muted/30"
                                )}
                            >
                                {isNote ? <FileText className={cn("w-3 h-3 shrink-0", activeDocumentId === doc.id ? "text-primary" : "text-muted-foreground")} /> : <Code2 className="w-3 h-3 shrink-0 text-blue-400" />}
                                <span className="text-[10px] font-bold uppercase tracking-tight truncate flex-1">{doc.title}</span>
                                <button
                                    onClick={(e) => { e.stopPropagation(); closeDocument(doc.id); }}
                                    className="p-0.5 rounded-md hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                    <X className="w-2.5 h-2.5" />
                                </button>
                            </div>
                        );
                    })}
                </div>

                {openDocuments.length > 0 && (
                    <button
                        onClick={closeAllDocuments}
                        className="flex items-center gap-1.5 px-2 py-1 rounded bg-muted/50 hover:bg-muted text-[8px] font-black uppercase tracking-widest text-muted-foreground hover:text-foreground transition-all border border-border/30"
                    >
                        <X className="w-2.5 h-2.5" />
                        Clear
                    </button>
                )}
            </div>

            {/* Toolbar */}
            <div className="flex items-center justify-between p-3 border-b border-border/50 bg-muted/10">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 min-w-[100px]">
                        {isSaving ? (
                            <span className="text-[10px] bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded font-bold animate-pulse">SAVING...</span>
                        ) : (
                            trimmedCurrent !== trimmedLast && trimmedCurrent.length > 0 && (
                                <span className="text-[10px] bg-yellow-500/10 text-yellow-500 px-2 py-0.5 rounded font-bold">UNSAVED</span>
                            )
                        )}
                        {!isSaving && trimmedCurrent === trimmedLast && trimmedCurrent.length > 0 && (
                            <span className="text-[10px] bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded font-bold">SAVED</span>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-1 bg-muted/90 p-1 rounded-sm">

                    <div className="flex items-center border-r border-border/50 pr-1 mr-1">
                        <Button
                            variant="ghost"
                            onClick={toggleMode}
                            className={cn("h-7 px-3 text-xs gap-2", "text-muted-foreground hover:text-foreground")}
                        >
                            {mode === 'wysiwyg' ? <Code2 className="w-2 h-2" /> : <Type className="w-2 h-2" />}
                            {/* {mode === 'wysiwyg' ? "Raw Source" : "Visual Editor"} */}
                        </Button>
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
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-foreground mr-1"
                        onClick={toggleZenMode}
                        title={isZenMode ? "Exit Full Width" : "Full Width"}
                    >
                        {isZenMode ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
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
                            /* Ensure scaled images are respected and not forced to 100% by prose */
                            .tiptap-editor-container .prose img {
                                display: block;
                                margin-left: auto;
                                margin-right: auto;
                                max-width: 100%;
                                height: auto;
                            }
                            /* If there is a width style, respect it */
                            .tiptap-editor-container .prose img[style*="width"] {
                                max-width: 100% !important;
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
