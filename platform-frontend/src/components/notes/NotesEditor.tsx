import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Node, mergeAttributes } from '@tiptap/core';
import Placeholder from '@tiptap/extension-placeholder';
import Image from '@tiptap/extension-image';
import { marked } from 'marked';
import TurndownService from 'turndown';
import { useAppStore } from '@/store';
import { Button } from "@/components/ui/button";
import {
    Loader2, Edit2, Eye, FileText, Code2, Type, Minus, Plus,
    Maximize2, Minimize2, X, ChevronDown, ChevronRight,
    List as ListIcon, SquarePlus, Bold, Italic, Strikethrough,
    Link as LinkIcon, ListOrdered, Superscript as SuperscriptIcon,
    Subscript as SubscriptIcon, Sigma, Underline as UnderlineIcon,
    Heading1, Heading2, Heading3, Heading4, Quote, Maximize
} from 'lucide-react';
import Subscript from '@tiptap/extension-subscript';
import Superscript from '@tiptap/extension-superscript';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

// Rules for Collapsible Sections (Details/Summary)
turndownService.addRule('details', {
    filter: 'details',
    replacement: (content, node: any) => {
        const isOpen = node.hasAttribute('open');
        return `<details${isOpen ? ' open' : ''}>\n${content}\n</details>`;
    }
});
turndownService.addRule('summary', {
    filter: 'summary',
    replacement: (content) => `<summary>${content}</summary>`
});
turndownService.addRule('detailsContent', {
    filter: (node) => node.nodeName === 'DIV' && node.classList.contains('details-content'),
    replacement: (content) => `<div class="details-content">\n\n${content}\n\n</div>`
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

// Custom Collapsible Section Extensions
const Details = Node.create({
    name: 'details',
    group: 'block',
    content: 'detailsSummary detailsContent',
    defining: true,
    addAttributes() {
        return {
            open: {
                default: false,
                parseHTML: element => element.hasAttribute('open'),
                renderHTML: attributes => (attributes.open ? { open: '' } : {}),
            },
        };
    },
    parseHTML() {
        return [{ tag: 'details' }];
    },
    renderHTML({ HTMLAttributes }) {
        return ['details', mergeAttributes(HTMLAttributes), 0];
    },
});

const DetailsSummary = Node.create({
    name: 'detailsSummary',
    group: 'block',
    content: 'text*',
    defining: true,
    parseHTML() {
        return [{ tag: 'summary' }];
    },
    renderHTML({ HTMLAttributes }) {
        return ['summary', mergeAttributes(HTMLAttributes), 0];
    },
});

const DetailsContent = Node.create({
    name: 'detailsContent',
    group: 'block',
    content: 'block+',
    defining: true,
    parseHTML() {
        return [{ tag: 'div', getAttrs: element => element.classList.contains('details-content') && {} }];
    },
    renderHTML({ HTMLAttributes }) {
        return ['div', mergeAttributes(HTMLAttributes, { class: 'details-content' }), 0];
    },
});

// WikiLink Extension (restored from previous)
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
    const [fontSize, setFontSize] = useState(24);

    // Derived state for comparison
    const trimmedCurrent = rawContent.trim();
    const trimmedLast = lastSavedContent.trim();

    const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const isFetchingRef = useRef(false);

    // Setup TipTap
    // Suggestion logic
    const [allNotes, setAllNotes] = useState<string[]>([]);

    // Focus active tab on change
    useEffect(() => {
        if (activeDocumentId) {
            const activeTab = document.getElementById(`tab-${activeDocumentId.replace(/[^a-zA-Z0-0]/g, '-')}`);
            if (activeTab) {
                activeTab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }
        }
    }, [activeDocumentId]);

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
            Details,
            DetailsSummary,
            DetailsContent,
            ScaledImage.configure({
                HTMLAttributes: {
                    class: 'rounded-lg border border-border/50 max-w-full h-auto my-4 shadow-sm cursor-pointer hover:shadow-md transition-shadow',
                },
            }),
            WikiLink.configure({
                suggestion: suggestionConfig,
            }),
            Underline,
            Subscript,
            Superscript,
            Link.configure({
                openOnClick: false,
                HTMLAttributes: {
                    class: 'text-primary underline cursor-pointer hover:text-primary/80 transition-colors',
                },
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

                // 1. Handle WikiLinks
                if (node?.type.name === 'wikilink') {
                    handleWikiLinkClick(node.attrs.id, node.attrs.targetLine, node.attrs.searchText);
                    return true;
                }

                // 2. Handle Collapsible Section Toggle
                const target = event.target as HTMLElement;
                const summary = target.closest('summary');
                if (summary) {
                    event.preventDefault();
                    event.stopImmediatePropagation();

                    const $pos = view.state.doc.resolve(pos);
                    // Search upwards for the details node
                    for (let d = $pos.depth; d > 0; d--) {
                        const parent = $pos.node(d);
                        if (parent.type.name === 'details') {
                            const startPos = $pos.before(d);
                            view.dispatch(view.state.tr.setNodeMarkup(startPos, undefined, {
                                ...parent.attrs,
                                open: !parent.attrs.open
                            }));
                            return true;
                        }
                    }
                }

                // 3. Handle standard TipTap Link clicks (marks)
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

    // Insert Collapsible Section
    const insertDetails = () => {
        if (editor) {
            editor.chain().focus().insertContent([
                {
                    type: 'details',
                    content: [
                        {
                            type: 'detailsSummary',
                            content: [{ type: 'text', text: 'Collapsible Section' }],
                        },
                        {
                            type: 'detailsContent',
                            content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Enter your collapsible content here...' }] }],
                        },
                    ],
                },
                {
                    type: 'paragraph',
                }
            ]).run();
        }
    };

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
            {/* Unified Commander Bar */}
            <div className="flex items-center justify-between border-b border-border bg-muted/20 px-2 shrink-0 h-12">
                {/* Left: Tabs Section */}
                <div className="flex items-center gap-[2px] h-full overflow-x-auto no-scrollbar scroll-smooth flex-1 active-tabs-container">
                    {openDocuments.map(doc => {
                        const isNote = doc.type === 'note' || doc.id.endsWith('.md');
                        const isActive = activeDocumentId === doc.id;
                        const isUnsaved = isActive && trimmedCurrent !== trimmedLast && trimmedCurrent.length > 0;
                        const isCurrentlySaving = isActive && isSaving;

                        return (
                            <div
                                key={doc.id}
                                id={`tab-${doc.id.replace(/[^a-zA-Z0-0]/g, '-')}`}
                                onClick={() => setActiveDocument(doc.id)}
                                className={cn(
                                    "group flex items-center gap-1.5 px-2 h-10 mt-auto pb-1 rounded-t-xl transition-all cursor-pointer border-x border-t border-transparent relative flex-shrink-0",
                                    isActive
                                        ? "bg-background border-border text-foreground z-10 before:absolute before:bottom-[-2px] before:left-0 before:right-0 before:h-[2px] before:bg-background shadow-[0_-2px_10px_rgba(0,0,0,0.08)]"
                                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                                )}
                            >
                                {isNote ? (
                                    <FileText className={cn("w-3.5 h-3.5 shrink-0 transition-colors", isActive ? "text-primary" : "text-muted-foreground/60")} />
                                ) : (
                                    <Code2 className="w-3.5 h-3.5 shrink-0 text-blue-400" />
                                )}
                                <span className="text-[10px] font-black uppercase tracking-wider whitespace-nowrap">{doc.title}</span>

                                <div className="flex items-center justify-center w-4 h-4">
                                    {isCurrentlySaving ? (
                                        <Loader2 className="w-2.5 h-2.5 animate-spin text-primary" />
                                    ) : isUnsaved ? (
                                        <div className="w-2 h-2 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)] animate-pulse" />
                                    ) : (
                                        <button
                                            onClick={(e) => { e.stopPropagation(); closeDocument(doc.id); }}
                                            className="p-0.5 rounded-md hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all transform hover:scale-110"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Right: Unified Controls Section */}
                <div className="flex items-center gap-0 pl-1 border-l border-border/30 ml-1">
                    <TooltipProvider delayDuration={200}>
                        {/* Unified Action Bar Section */}
                        <div className="flex items-center bg-muted/50 rounded-lg p-0.5 border border-border/30 mr-1 overflow-hidden">

                            {/* Headings Dropdown */}
                            <DropdownMenu>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" size="sm" className="h-7 px-1.5 text-[10px] font-bold text-muted-foreground hover:text-foreground">
                                                <Type className="w-3.5 h-3.5 mr-1" />
                                                <ChevronDown className="w-3 h-3 opacity-50" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Text Style</TooltipContent>
                                </Tooltip>
                                <DropdownMenuContent align="start" className="w-40 glass-panel border-border/30 bg-background/80 backdrop-blur-xl">
                                    <DropdownMenuItem onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} className="flex items-center gap-2 text-xs cursor-pointer">
                                        <Heading1 className="w-3.5 h-3.5" /> Heading 1
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className="flex items-center gap-2 text-xs cursor-pointer">
                                        <Heading2 className="w-3.5 h-3.5" /> Heading 2
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} className="flex items-center gap-2 text-xs cursor-pointer">
                                        <Heading3 className="w-3.5 h-3.5" /> Heading 3
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => editor.chain().focus().setParagraph().run()} className="flex items-center gap-2 text-xs cursor-pointer">
                                        <Type className="w-3.5 h-3.5" /> Paragraph
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>

                            <div className="w-[1px] h-3 bg-border/50 mx-[0px]" />

                            {/* Formatting Group */}
                            <div className="flex items-center">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleBold().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('bold') && "bg-primary/20 text-primary")}
                                        >
                                            <Bold className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Bold (Ctrl+B)</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleItalic().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('italic') && "bg-primary/20 text-primary")}
                                        >
                                            <Italic className="w-4 h-4" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Italic (Ctrl+I)</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleUnderline().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('underline') && "bg-primary/20 text-primary")}
                                        >
                                            <UnderlineIcon className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Underline (Ctrl+U)</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleStrike().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('strike') && "bg-primary/20 text-primary")}
                                        >
                                            <Strikethrough className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Strikethrough</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleCode().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('code') && "bg-primary/20 text-primary")}
                                        >
                                            <Code2 className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Inline Code</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                                const url = window.prompt('URL');
                                                if (url) editor.chain().focus().setLink({ href: url }).run();
                                            }}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('link') && "bg-primary/20 text-primary")}
                                        >
                                            <LinkIcon className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Link</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleBulletList().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('bulletList') && "bg-primary/20 text-primary")}
                                        >
                                            <ListIcon className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Bullet List</TooltipContent>
                                </Tooltip>
                            </div>

                            <div className="w-[1px] h-3 bg-border/50 mx-[1px]" />

                            {/* Scripting Group */}
                            <div className="flex items-center">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleSubscript().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('subscript') && "bg-primary/20 text-primary")}
                                        >
                                            <SubscriptIcon className="w-4 h-4" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Subscript</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().toggleSuperscript().run()}
                                            className={cn("h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all", editor.isActive('superscript') && "bg-primary/20 text-primary")}
                                        >
                                            <SuperscriptIcon className="w-4 h-4" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Superscript</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => editor.chain().focus().insertContent('$$ LaTeX $$').run()}
                                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground transition-all"
                                        >
                                            <Sigma className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Latex Block</TooltipContent>
                                </Tooltip>
                            </div>

                            <div className="w-[1px] h-3 bg-border/50 mx-[1px]" />

                            {/* Structures Group */}
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={insertDetails}
                                        className="h-7 px-1.5 text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all"
                                    >
                                        <SquarePlus className="w-3.5 h-3.5" />
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom">Collapsible Section</TooltipContent>
                            </Tooltip>

                            <div className="w-[1px] h-3 bg-border/50 mx-[1px]" />

                            {/* View Controls Group */}
                            <div className="flex items-center">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={toggleMode}
                                            className={cn(
                                                "h-7 px-2 text-[10px] font-bold uppercase tracking-widest gap-1 transition-all border border-transparent",
                                                mode === 'wysiwyg' ? "bg-white/10 text-foreground border-primary/30" : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                                            )}
                                        >
                                            {mode === 'wysiwyg' ? <Eye className="w-3.5 h-3.5 text-primary" /> : <Code2 className="w-3.5 h-3.5" />}
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Toggle View Mode</TooltipContent>
                                </Tooltip>

                                <div className="w-[1px] h-3 bg-border/50 mx-[1px]" />

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 text-muted-foreground hover:text-foreground transition-all hover:bg-white/5"
                                            onClick={() => setFontSize(s => Math.max(12, s - 1))}
                                        >
                                            <Minus className="w-3 h-3" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Font Smaller</TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 text-muted-foreground hover:text-foreground transition-all focus:scale-110 hover:bg-white/5"
                                            onClick={() => setFontSize(s => Math.min(32, s + 1))}
                                        >
                                            <Plus className="w-3 h-3" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Font Bigger</TooltipContent>
                                </Tooltip>

                                <div className="w-[1px] h-3 bg-border/50 mx-[1px]" />

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn(
                                                "h-7 w-7 transition-all text-muted-foreground hover:text-foreground hover:bg-white/5",
                                                isZenMode && "text-primary bg-primary/10"
                                            )}
                                            onClick={toggleZenMode}
                                        >
                                            {isZenMode ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Zen Mode</TooltipContent>
                                </Tooltip>

                                <div className="w-[1px] h-3 bg-border/50 mx-0.5" />

                                {/* Clear All Inside the same box */}
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={closeAllDocuments}
                                            className="h-7 px-2 text-[10px] font-black uppercase tracking-[0.1em] text-muted-foreground hover:text-red-400 hover:bg-red-400/10 transition-all gap-1"
                                        >
                                            <X className="w-3.5 h-3.5" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent side="bottom">Close All Tabs</TooltipContent>
                                </Tooltip>
                            </div>
                        </div>
                    </TooltipProvider>
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
                            .tiptap-editor-container .prose li {
                                font-size: inherit !important;
                            }
                            .tiptap-editor-container .prose h1 {
                                font-size: 2.5em !important;
                                font-weight: 800;
                                margin-top: 1.5em;
                                margin-bottom: 0.5em;
                                line-height: 1.2;
                            }
                            .tiptap-editor-container .prose h2 {
                                font-size: 1.8em !important;
                                font-weight: 700;
                                margin-top: 1.2em;
                                margin-bottom: 0.4em;
                                line-height: 1.3;
                            }
                            .tiptap-editor-container .prose h3 {
                                font-size: 1.4em !important;
                                font-weight: 600;
                                margin-top: 1em;
                                margin-bottom: 0.3em;
                                line-height: 1.4;
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
                            /* Hide Tailwind Prose backticks in inline code */
                            .tiptap-editor-container .prose code::before,
                            .tiptap-editor-container .prose code::after {
                                content: "" !important;
                            }
                            .tiptap-editor-container .prose code {
                                background: hsl(var(--primary) / 0.1);
                                padding: 0.2rem 0.4rem;
                                rounded: 0.375rem;
                                font-weight: 500;
                            }
                            /* Details Styling */
                            .tiptap-editor-container details {
                                margin: 1rem 0;
                                padding: 0.5rem 1rem;
                                border: 1px solid hsl(var(--border) / 0.5);
                                border-radius: 0.75rem;
                                background: hsl(var(--muted) / 0.2);
                                transition: all 0.2s ease;
                            }
                            .tiptap-editor-container details[open] {
                                background: hsl(var(--muted) / 0.4);
                                border-color: hsl(var(--primary) / 0.3);
                            }
                            .tiptap-editor-container summary {
                                cursor: pointer;
                                font-weight: 700;
                                font-size: 0.85rem;
                                text-transform: uppercase;
                                letter-spacing: 0.05em;
                                color: hsl(var(--muted-foreground));
                                outline: none;
                                list-style: none;
                                display: flex;
                                items-center: center;
                                gap: 0.5rem;
                            }
                            .tiptap-editor-container summary::-webkit-details-marker {
                                display: none;
                            }
                            .tiptap-editor-container summary::before {
                                content: '→';
                                display: inline-block;
                                transition: transform 0.2s ease;
                                color: hsl(var(--primary));
                            }
                            .tiptap-editor-container details[open] > summary::before {
                                transform: rotate(90deg);
                            }
                            .tiptap-editor-container .details-content {
                                padding-top: 1rem;
                                margin-top: 0.5rem;
                                border-top: 1px solid hsl(var(--border) / 0.3);
                            }
                        `}</style>
                        <div className="tiptap-editor-container h-full">
                            <EditorContent editor={editor} />
                        </div>
                    </div>
                )}
            </div >
        </div >
    );

    // Helper to update raw content and sync if needed
    function setContentRaw(val: string) {
        setRawContent(val);
        // If in raw mode, we don't update editor immediately to avoid cursor jumping, 
        // we update editor only when switching back
    }
};
