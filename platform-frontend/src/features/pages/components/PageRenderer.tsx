import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
    BarChart2,
    Calculator,
    Check,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    CloudSun,
    Copy,
    Download,
    Edit2,
    ExternalLink,
    Globe,
    History,
    Loader2,
    Lock,
    MessageSquare,
    Plus,
    Send,
    Share2,
    Vote,
    X,
    Zap
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';

interface PageSection {
    id: string;
    title: string;
    content: string;
    blocks: Array<{
        type?: 'text' | 'table' | 'chart' | 'media';
        kind?: string;
        content?: any;
        [key: string]: any;
    }>;
    charts?: Array<{
        chart_id: string;
        type: string;
        title: string;
        chart_data?: any;
    }>;
    citations: string[];
    metadata?: {
        enhanced?: boolean;
        confidence_score?: number;
    };
}

interface PageData {
    id: string;
    query: string;
    template: string;
    status: string;
    sections: PageSection[];
    citations: Array<{
        id: string;
        url: string;
        title: string;
        snippet?: string;
    }>;
    metadata: {
        created_at: string;
        created_by: string;
        version?: number;
    };
}

interface PageRendererProps {
    page: PageData;
    isEditable?: boolean;
    onSectionRefine?: (sectionId: string) => void;
    onExport?: (format: string) => void;
}

export const PageRenderer: React.FC<PageRendererProps> = ({
    page,
    isEditable = false,
    onSectionRefine,
    onExport
}) => {
    const [expandedSections, setExpandedSections] = useState<Set<string>>(
        new Set(page.sections.map(s => s.id))
    );
    const [localSections, setLocalSections] = useState(() => page.sections);
    const [copiedCitation, setCopiedCitation] = useState<string | null>(null);
    const [showExportMenu, setShowExportMenu] = useState(false);
    const [exportingFormat, setExportingFormat] = useState<string | null>(null);
    const [showShareDialog, setShowShareDialog] = useState(false);
    const [sharePassword, setSharePassword] = useState('');
    const [sharePasswordEnabled, setSharePasswordEnabled] = useState(false);
    const [shareLoading, setShareLoading] = useState(false);
    const [generatedShareUrl, setGeneratedShareUrl] = useState<string | null>(null);
    const [copiedShareUrl, setCopiedShareUrl] = useState(false);
    const [showAddWidgetDialog, setShowAddWidgetDialog] = useState(false);
    const [addingWidget, setAddingWidget] = useState(false);
    const [isEditMode, setIsEditMode] = useState(false);
    const [showCitations, setShowCitations] = useState(true);
    const [showPageCopilot, setShowPageCopilot] = useState(false);
    const [copilotInput, setCopilotInput] = useState('');
    const [copilotMessages, setCopilotMessages] = useState<Array<{role: 'user' | 'assistant'; text: string}>>([]);
    const [copilotLoading, setCopilotLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);

    const slug = page.query.slice(0, 40).replace(/[^a-z0-9]/gi, '-').toLowerCase();

    const handleExport = async (format: string) => {
        setExportingFormat(format);
        setShowExportMenu(false);

        if (format === 'markdown') {
            try {
                const blob = new Blob([generateMarkdown(page)], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `${slug}.md`; a.click();
                URL.revokeObjectURL(url);
            } catch (e) { console.error(e); } finally { setExportingFormat(null); }
            return;
        }

        if (format === 'html') {
            try {
                const blob = new Blob([generateHtml(page)], { type: 'text/html' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `${slug}.html`; a.click();
                URL.revokeObjectURL(url);
            } catch (e) { console.error(e); } finally { setExportingFormat(null); }
            return;
        }

        if (format === 'pdf') {
            try {
                const el = contentRef.current;
                if (!el) { setExportingFormat(null); return; }
                const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
                    import('jspdf'),
                    import('html2canvas'),
                ]);
                const canvas = await html2canvas(el, { scale: 2, useCORS: true, backgroundColor: '#09090b' });
                const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
                const pageWidth = pdf.internal.pageSize.getWidth();
                const pageHeight = pdf.internal.pageSize.getHeight();
                const imgW = pageWidth;
                const imgH = (canvas.height * imgW) / canvas.width;
                let yOffset = 0;
                let remaining = imgH;
                while (remaining > 0) {
                    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, -yOffset, imgW, imgH);
                    remaining -= pageHeight;
                    yOffset += pageHeight;
                    if (remaining > 0) pdf.addPage();
                }
                pdf.save(`${slug}.pdf`);
            } catch (e) { console.error('PDF export error:', e); } finally { setExportingFormat(null); }
            return;
        }

        if (format === 'docx') {
            try {
                const { Document, Packer, Paragraph, TextRun, HeadingLevel } = await import('docx');
                const children: any[] = [
                    new Paragraph({ text: page.query, heading: HeadingLevel.TITLE }),
                    new Paragraph({ text: '' }),
                ];
                for (const section of page.sections) {
                    children.push(new Paragraph({ text: section.title, heading: HeadingLevel.HEADING_1 }));
                    for (const block of section.blocks) {
                        const text =
                            block.kind === 'markdown' ? block.text :
                            block.kind === 'highlight' ? `${block.metric}: ${block.value}` :
                            block.kind === 'insight' ? `${block.title} — ${block.content}` :
                            block.type === 'text' ? block.content : null;
                        if (text) children.push(new Paragraph({ children: [new TextRun(String(text))] }));
                    }
                    children.push(new Paragraph({ text: '' }));
                }
                if (page.citations.length) {
                    children.push(new Paragraph({ text: 'References', heading: HeadingLevel.HEADING_2 }));
                    page.citations.forEach((c, i) =>
                        children.push(new Paragraph({ children: [new TextRun(`[${i + 1}] ${c.title || c.id} — ${c.url}`)] }))
                    );
                }
                const doc = new Document({ sections: [{ properties: {}, children }] });
                const blob = await Packer.toBlob(doc);
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `${slug}.docx`; a.click();
                URL.revokeObjectURL(url);
            } catch (e) { console.error('DOCX export error:', e); } finally { setExportingFormat(null); }
            return;
        }

        setExportingFormat(null);
    };

    const handleShare = () => {
        setGeneratedShareUrl(null);
        setSharePassword('');
        setSharePasswordEnabled(false);
        setCopiedShareUrl(false);
        setShowShareDialog(true);
    };

    const handleGenerateShareLink = async () => {
        setShareLoading(true);
        try {
            const res = await fetch(`${API_BASE}/pages/${page.id}/actions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'share',
                    share_type: 'link',
                    password: sharePasswordEnabled && sharePassword ? sharePassword : undefined,
                }),
            });
            const data = await res.json();
            if (data.job_id) {
                const jobRes = await fetch(`${API_BASE}/pages/actions/${data.job_id}`);
                const jobData = await jobRes.json();
                if (jobData.share_url) {
                    const token = jobData.share_url.replace('/shared/', '');
                    setGeneratedShareUrl(`${window.location.origin}/shared/${token}`);
                }
            }
        } catch (e) {
            console.error('Share error:', e);
        } finally {
            setShareLoading(false);
        }
    };

    const handleAddWidget = async (widgetType: string, config: Record<string, unknown>) => {
        setAddingWidget(true);
        try {
            const res = await fetch(`${API_BASE}/pages/${page.id}/widgets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ widget_type: widgetType, config }),
            });
            const data = await res.json();
            // Optimistically append to section 0 so it shows immediately
            const newWidget = {
                id: data.widget_id,
                type: widgetType,
                widget_type: widgetType,
                config,
                active: true,
            };
            setLocalSections(prev =>
                prev.map((s, i) =>
                    i === 0
                        ? { ...s, widgets: [...((s as any).widgets || []), newWidget] }
                        : s
                )
            );
            setShowAddWidgetDialog(false);
        } catch (e) {
            console.error('Add widget error:', e);
        } finally {
            setAddingWidget(false);
        }
    };

    const handlePageCopilot = async (directMsg?: string) => {
        const userMsg = directMsg ?? copilotInput.trim();
        if (!userMsg) return;
        setCopilotMessages(prev => [...prev, { role: 'user', text: userMsg }]);
        if (!directMsg) setCopilotInput('');
        setCopilotLoading(true);
        try {
            const res = await fetch(
                `${API_BASE}/pages/${page.id}/copilot/chat?message=${encodeURIComponent(userMsg)}}`,
                { method: 'POST' }
            );
            const data = await res.json();
            setCopilotMessages(prev => [...prev, { role: 'assistant', text: data.response || 'No response received.' }]);
        } catch (e) {
            setCopilotMessages(prev => [...prev, { role: 'assistant', text: 'Sorry, failed to get a response.' }]);
        } finally {
            setCopilotLoading(false);
        }
    };

    // Auto-scroll copilot messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [copilotMessages, copilotLoading]);

    // Route a section refine action into the page copilot
    const handleSendToCopilot = (message: string) => {
        setShowPageCopilot(true);
        handlePageCopilot(message);
    };

    const toggleSection = (sectionId: string) => {
        setExpandedSections(prev => {
            const next = new Set(prev);
            if (next.has(sectionId)) {
                next.delete(sectionId);
            } else {
                next.add(sectionId);
            }
            return next;
        });
    };

    const copyCitation = (citation: string) => {
        navigator.clipboard.writeText(citation);
        setCopiedCitation(citation);
        setTimeout(() => setCopiedCitation(null), 2000);
    };

    return (
        <div className="relative h-full flex flex-col bg-background">
            {/* Header */}
            <div className="border-b border-border/50 p-4 space-y-3">
                <div className="flex items-start justify-between">
                    <div className="flex-1">
                        <h1 className="text-2xl font-bold mb-2">{page.query}</h1>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground">
                            <Badge variant="outline">{page.template}</Badge>
                            <span>{localSections.length} sections</span>
                            <span>{page.citations.length} sources</span>
                            <span>
                                Updated {formatDistanceToNow(new Date(page.metadata.created_at), { addSuffix: true })}
                            </span>
                        </div>
                    </div>

                    <div className="flex gap-2 items-center">
                        <div className="relative">
                            <Button variant="outline" size="sm" onClick={() => setShowExportMenu(!showExportMenu)}>
                                {exportingFormat ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                                Export
                            </Button>
                            {showExportMenu && (
                                <div className="absolute right-0 top-full mt-1 bg-popover border border-border rounded-lg shadow-lg z-50 w-36">
                                    {(['pdf', 'markdown', 'html', 'docx'] as const).map(fmt => (
                                        <button
                                            key={fmt}
                                            onClick={() => handleExport(fmt)}
                                            className="w-full text-left px-4 py-2 text-sm hover:bg-accent first:rounded-t-lg last:rounded-b-lg"
                                        >
                                            {fmt.toUpperCase()}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                        <Button variant="outline" size="sm" onClick={handleShare}>
                            <Share2 className="w-4 h-4 mr-2" />
                            Share
                        </Button>
                        {isEditable && (
                            <Button
                                variant={isEditMode ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setIsEditMode(m => !m)}
                            >
                                {isEditMode
                                    ? <><X className="w-4 h-4 mr-2" />Done Editing</>
                                    : <><Edit2 className="w-4 h-4 mr-2" />Edit Page</>
                                }
                            </Button>
                        )}
                        {isEditable && isEditMode && (
                            <Button variant="outline" size="sm" onClick={() => setShowAddWidgetDialog(true)}>
                                <Plus className="w-4 h-4 mr-2" />
                                Add Widget
                            </Button>
                        )}
                        <Button variant="outline" size="sm">
                            <History className="w-4 h-4 mr-2" />
                            History
                        </Button>
                        <Button
                            variant={showPageCopilot ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setShowPageCopilot(!showPageCopilot)}
                        >
                            <MessageSquare className="w-4 h-4 mr-2" />
                            Copilot
                        </Button>
                    </div>
                </div>


            </div>

            {/* Content */}
            <div className="flex-1 flex overflow-hidden">
                {/* Main Content */}
                <ScrollArea className="flex-1">
                    <div ref={contentRef} className="max-w-4xl mx-auto p-6 space-y-6">
                        {localSections.map((section) => (
                            <SectionBlock
                                key={section.id}
                                section={section}
                                isExpanded={expandedSections.has(section.id)}
                                onToggle={() => toggleSection(section.id)}
                                onRequestCopilot={handleSendToCopilot}
                                pageId={page.id}
                                isEditMode={isEditMode}
                                onSectionSaved={(updated) =>
                                    setLocalSections(prev =>
                                        prev.map(s => s.id === updated.id ? { ...s, ...updated } : s)
                                    )
                                }
                            />
                        ))}
                    </div>
                </ScrollArea>

                {/* Citations Sidebar */}
                <div className={cn("border-l border-border/50 flex flex-col transition-all", showCitations ? 'w-80' : 'w-10')}>
                    <div className="p-3 border-b border-border/50 flex items-center justify-between">
                        {showCitations && (
                            <div>
                                <h3 className="font-semibold text-sm">Sources & Citations</h3>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    {page.citations.length} references
                                </p>
                            </div>
                        )}
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 shrink-0"
                            onClick={() => setShowCitations(!showCitations)}
                            title={showCitations ? 'Collapse citations' : 'Expand citations'}
                        >
                            {showCitations ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                        </Button>
                    </div>

                    {showCitations && <ScrollArea className="flex-1 p-4">
                        <div className="space-y-3">
                            {page.citations.map((citation, idx) => (
                                <div
                                    key={citation.id}
                                    className="p-3 rounded-lg border border-border/50 hover:border-primary/50 transition-colors"
                                >
                                    <div className="flex items-start justify-between mb-2">
                                        <Badge variant="outline" className="text-xs">
                                            [{idx + 1}]
                                        </Badge>
                                        <div className="flex gap-1">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 w-6 p-0"
                                                onClick={() => copyCitation(citation.url)}
                                            >
                                                {copiedCitation === citation.url ? (
                                                    <Check className="w-3 h-3 text-green-500" />
                                                ) : (
                                                    <Copy className="w-3 h-3" />
                                                )}
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 w-6 p-0"
                                                asChild
                                            >
                                                <a href={citation.url} target="_blank" rel="noopener noreferrer">
                                                    <ExternalLink className="w-3 h-3" />
                                                </a>
                                            </Button>
                                        </div>
                                    </div>

                                    <h4 className="font-medium text-sm mb-1 line-clamp-2">
                                        {citation.title}
                                    </h4>

                                    {citation.snippet && (
                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                            {citation.snippet}
                                        </p>
                                    )}

                                    <p className="text-xs text-muted-foreground mt-2 truncate">
                                        {new URL(citation.url).hostname}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>}
                </div>
            </div>

            {/* Share Dialog */}
            {showShareDialog && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowShareDialog(false)}>
                    <div className="bg-background border border-border rounded-xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <Globe className="w-5 h-5 text-primary" />
                                <h3 className="font-semibold text-base">Share Page</h3>
                            </div>
                            <button onClick={() => setShowShareDialog(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <label className="flex items-center gap-3 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={sharePasswordEnabled}
                                    onChange={e => setSharePasswordEnabled(e.target.checked)}
                                    className="w-4 h-4 accent-primary"
                                />
                                <div className="flex items-center gap-2 text-sm">
                                    <Lock className="w-4 h-4 text-muted-foreground" />
                                    Password protect this link
                                </div>
                            </label>

                            {sharePasswordEnabled && (
                                <input
                                    type="password"
                                    placeholder="Enter a password…"
                                    value={sharePassword}
                                    onChange={e => setSharePassword(e.target.value)}
                                    className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-lg outline-none focus:ring-2 focus:ring-primary/40"
                                />
                            )}

                            {!generatedShareUrl ? (
                                <Button
                                    className="w-full"
                                    onClick={handleGenerateShareLink}
                                    disabled={shareLoading || (sharePasswordEnabled && !sharePassword)}
                                >
                                    {shareLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Globe className="w-4 h-4 mr-2" />}
                                    {shareLoading ? 'Generating…' : 'Generate Share Link'}
                                </Button>
                            ) : (
                                <div className="space-y-2">
                                    <p className="text-xs text-muted-foreground">Anyone with this link {sharePasswordEnabled ? '(and the password) ' : ''}can view this page:</p>
                                    <div className="flex items-center gap-2">
                                        <input
                                            readOnly
                                            value={generatedShareUrl}
                                            className="flex-1 px-3 py-2 text-xs bg-muted border border-border rounded-lg outline-none select-all"
                                            onClick={e => (e.target as HTMLInputElement).select()}
                                        />
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => {
                                                navigator.clipboard.writeText(generatedShareUrl);
                                                setCopiedShareUrl(true);
                                                setTimeout(() => setCopiedShareUrl(false), 2000);
                                            }}
                                        >
                                            {copiedShareUrl ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                                        </Button>
                                    </div>
                                    {copiedShareUrl && <p className="text-xs text-green-500">✓ Copied to clipboard</p>}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Add Widget Dialog */}
            {showAddWidgetDialog && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowAddWidgetDialog(false)}>
                    <div className="bg-background border border-border rounded-xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <Zap className="w-5 h-5 text-primary" />
                                <h3 className="font-semibold text-base">Add Live Widget</h3>
                            </div>
                            <button onClick={() => setShowAddWidgetDialog(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <p className="text-xs text-muted-foreground mb-4">Choose a live widget to embed in the first section of this page.</p>
                        <div className="grid grid-cols-2 gap-3">
                            {([
                                { type: 'weather', label: 'Weather', icon: CloudSun, config: { lat: 40.71, lon: -74.01, city: 'New York' } },
                                { type: 'stock_ticker', label: 'Stock Ticker', icon: BarChart2, config: { symbols: ['AAPL', 'GOOGL', 'MSFT'] } },
                                { type: 'live_chart', label: 'Live Chart', icon: Zap, config: { title: 'Live Metrics', interval: 5 } },
                                { type: 'poll', label: 'Poll', icon: Vote, config: { question: 'What do you think?', options: ['Option A', 'Option B', 'Option C'] } },
                                { type: 'calculator', label: 'Calculator', icon: Calculator, config: {} },
                            ] as const).map(({ type, label, icon: Icon, config }) => (
                                <button
                                    key={type}
                                    disabled={addingWidget}
                                    onClick={() => handleAddWidget(type, config)}
                                    className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 transition-all text-sm font-medium disabled:opacity-50"
                                >
                                    {addingWidget ? <Loader2 className="w-5 h-5 animate-spin text-primary" /> : <Icon className="w-5 h-5 text-primary" />}
                                    {label}
                                </button>
                            ))}
                        </div>
                        <p className="text-xs text-muted-foreground mt-4 text-center">Widgets are added to <strong>Section 1</strong> (Overview). Reopen the page from the sidebar to see it.</p>
                    </div>
                </div>
            )}

            {/* Floating Copilot Card */}
            {showPageCopilot && (
                <div className="absolute bottom-6 right-6 z-50 w-96 flex flex-col bg-background border border-border rounded-xl shadow-2xl overflow-hidden" style={{ maxHeight: '520px' }}>
                    {/* Card Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/40 shrink-0">
                        <div className="flex items-center gap-2">
                            <MessageSquare className="w-4 h-4 text-primary" />
                            <span className="font-semibold text-sm">Page Copilot</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0"
                            onClick={() => setShowPageCopilot(false)}
                        >
                            <X className="w-4 h-4" />
                        </Button>
                    </div>

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ minHeight: '200px' }}>
                        {copilotMessages.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-8">
                                Ask anything about this page…
                            </p>
                        )}
                        {copilotMessages.map((msg, idx) => (
                            <div key={idx} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                                <div className={cn(
                                    'max-w-[80%] rounded-xl px-3 py-2 text-sm leading-relaxed',
                                    msg.role === 'user'
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-muted border border-border/50'
                                )}>
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                        {copilotLoading && (
                            <div className="flex justify-start">
                                <div className="bg-muted border border-border/50 rounded-xl px-3 py-2">
                                    <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div className="p-3 border-t border-border flex gap-2 shrink-0 bg-background">
                        <input
                            type="text"
                            value={copilotInput}
                            onChange={(e) => setCopilotInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handlePageCopilot()}
                            placeholder="Ask a follow-up question…"
                            className="flex-1 px-3 py-2 bg-muted/50 border border-border/50 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                            autoFocus
                        />
                        <Button
                            size="sm"
                            onClick={handlePageCopilot}
                            disabled={copilotLoading || !copilotInput.trim()}
                        >
                            {copilotLoading ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <Send className="w-4 h-4" />
                            )}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
};

const SectionBlock: React.FC<{
    section: PageSection;
    isExpanded: boolean;
    onToggle: () => void;
    onRequestCopilot?: (message: string) => void;
    pageId: string;
    isEditMode?: boolean;
    onSectionSaved?: (updated: PageSection) => void;
}> = ({ section, isExpanded, onToggle, onRequestCopilot, pageId, isEditMode = false, onSectionSaved }) => {
    const [showCopilot, setShowCopilot] = useState(false);
    const [showRefineMenu, setShowRefineMenu] = useState(false);
    const [copilotQuery, setCopilotQuery] = useState('');
    const [copilotReply, setCopilotReply] = useState<string | null>(null);
    const [copilotLoading, setCopilotLoading] = useState(false);

    // Edit mode state
    const [editedTitle, setEditedTitle] = useState(section.title);
    const [editedBlocks, setEditedBlocks] = useState<any[]>(section.blocks);
    const [saveLoading, setSaveLoading] = useState(false);
    const [saveSuccess, setSaveSuccess] = useState(false);

    // Sync edit buffers when section prop changes
    useEffect(() => {
        setEditedTitle(section.title);
        setEditedBlocks(section.blocks);
    }, [section.id]);

    const handleSave = async () => {
        setSaveLoading(true);
        try {
            await fetch(`${API_BASE}/pages/${pageId}/sections/${section.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: editedTitle, blocks: editedBlocks }),
            });
            onSectionSaved?.({ ...section, title: editedTitle, blocks: editedBlocks } as PageSection);
            setSaveSuccess(true);
            setTimeout(() => setSaveSuccess(false), 2000);
        } catch (e) {
            console.error('Save section error:', e);
        } finally {
            setSaveLoading(false);
        }
    };

    const handleCancel = () => {
        setEditedTitle(section.title);
        setEditedBlocks(section.blocks);
    };

    const handleSectionCopilot = async () => {
        if (!copilotQuery.trim()) return;
        setCopilotLoading(true);
        try {
            const res = await fetch(
                `${API_BASE}/pages/${pageId}/copilot/chat?message=${encodeURIComponent(copilotQuery)}`,
                { method: 'POST' }
            );
            const data = await res.json();
            setCopilotReply(data.response);
            setCopilotQuery('');
        } catch (e) {
            console.error('Section copilot error:', e);
        } finally {
            setCopilotLoading(false);
        }
    };

    return (
        <div className="border border-border/50 rounded-lg overflow-hidden group">
            {/* Section Header */}
            <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={isEditMode ? undefined : onToggle}
            >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                    {!isEditMode && (
                        isExpanded
                            ? <ChevronDown className="w-5 h-5 text-muted-foreground shrink-0" />
                            : <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0" />
                    )}
                    {isEditMode ? (
                        <input
                            value={editedTitle}
                            onChange={e => setEditedTitle(e.target.value)}
                            onClick={e => e.stopPropagation()}
                            className="flex-1 text-xl font-semibold bg-muted border border-primary/40 rounded-md px-2 py-0.5 outline-none focus:ring-2 focus:ring-primary/40"
                        />
                    ) : (
                        <h2 className="text-xl font-semibold">{section.title}</h2>
                    )}
                    {section.metadata?.enhanced && (
                        <Badge variant="secondary" className="text-xs shrink-0">Enhanced</Badge>
                    )}
                </div>

                <div className={`flex gap-2 ${isEditMode ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}>
                    ) : (<>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                            e.stopPropagation();
                            setShowCopilot(!showCopilot);
                            setShowRefineMenu(false);
                        }}
                    >
                        <MessageSquare className="w-4 h-4" />
                    </Button>
                    <div className="relative">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowRefineMenu(m => !m);
                                setShowCopilot(false);
                            }}
                        >
                            <Edit2 className="w-4 h-4" />
                        </Button>
                        {showRefineMenu && (
                            <div
                                className="absolute right-0 top-full mt-1 bg-popover border border-border rounded-lg shadow-lg z-50 py-1 w-40"
                                onClick={e => e.stopPropagation()}
                            >
                                {([
                                    { label: '↑ Expand', msg: 'expand' },
                                    { label: '↓ Simplify', msg: 'simplify' },
                                    { label: '+ Add Examples', msg: 'add concrete examples' },
                                    { label: '📚 More Sources', msg: 'add more citations and sources' },
                                ] as const).map(({ label, msg }) => (
                                    <button
                                        key={msg}
                                        onClick={() => {
                                            setShowRefineMenu(false);
                                            onRequestCopilot?.(`[${section.title}] Please ${msg} for this section.`);
                                        }}
                                        className="w-full text-left px-3 py-2 text-sm hover:bg-accent first:rounded-t-lg last:rounded-b-lg"
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    </>)}
                </div>
            </div>

            {/* Section Content */}
            {(isExpanded || isEditMode) && (
                <div className="p-4 pt-0 space-y-4">
                    {(isEditMode ? editedBlocks : section.blocks).map((block, idx) => (
                        isEditMode && (block.kind === 'markdown' || block.type === 'text') ? (
                            <textarea
                                key={idx}
                                value={block.kind === 'markdown' ? block.text : block.content}
                                onChange={e => {
                                    const val = e.target.value;
                                    setEditedBlocks(prev => prev.map((b, i) =>
                                        i === idx
                                            ? block.kind === 'markdown'
                                                ? { ...b, text: val }
                                                : { ...b, content: val }
                                            : b
                                    ));
                                }}
                                rows={6}
                                className="w-full px-3 py-2 text-sm bg-muted border border-primary/30 rounded-lg resize-y outline-none focus:ring-2 focus:ring-primary/40 font-mono"
                            />
                        ) : isEditMode && block.kind === 'insight' ? (
                            <div key={idx} className="space-y-1">
                                <input
                                    value={block.title}
                                    onChange={e => {
                                        const val = e.target.value;
                                        setEditedBlocks(prev => prev.map((b, i) => i === idx ? { ...b, title: val } : b));
                                    }}
                                    placeholder="Insight title"
                                    className="w-full px-2 py-1 text-sm font-medium bg-muted border border-primary/30 rounded outline-none focus:ring-2 focus:ring-primary/40"
                                />
                                <textarea
                                    value={block.content}
                                    onChange={e => {
                                        const val = e.target.value;
                                        setEditedBlocks(prev => prev.map((b, i) => i === idx ? { ...b, content: val } : b));
                                    }}
                                    rows={3}
                                    className="w-full px-2 py-1 text-sm bg-muted border border-primary/30 rounded-lg resize-y outline-none focus:ring-2 focus:ring-primary/40"
                                />
                            </div>
                        ) : (
                            <ContentBlock key={idx} block={isEditMode ? editedBlocks[idx] : block} />
                        )
                    ))}

                    {/* Chart visualizations */}
                    {section.charts && section.charts.length > 0 && (
                        <div className="space-y-4">
                            {section.charts.map((chart) => (
                                <ChartBlock key={chart.chart_id} chart={chart} />
                            ))}
                        </div>
                    )}

                    {/* Live Widgets */}
                    {(section as any).widgets && (section as any).widgets.length > 0 && (
                        <div className="space-y-3">
                            {((section as any).widgets as any[]).filter((w: any) => w.active !== false).map((widget: any) => (
                                <LiveWidget key={widget.id || widget.widget_type} widget={widget} />
                            ))}
                        </div>
                    )}

                    {/* Section Citations */}
                    {section.citations && section.citations.length > 0 && (
                        <div className="text-xs text-muted-foreground space-x-2 pt-2 border-t border-border/50">
                            <span className="font-medium">Sources:</span>
                            {section.citations.map((cit, idx) => (
                                <span key={idx}>[{cit}]</span>
                            ))}
                        </div>
                    )}

                    {/* Section Refinement Actions — removed: now routed to page copilot via ✏️ dropdown */}

                    {/* Inline Copilot */}
                    {showCopilot && (
                        <div className="mt-4 p-4 bg-muted/50 rounded-lg border border-border/50">
                            <div className="flex items-center gap-2 mb-3">
                                <MessageSquare className="w-4 h-4 text-primary" />
                                <span className="font-medium text-sm">Ask about this section</span>
                            </div>
                            {copilotReply && (
                                <div className="mb-3 p-3 bg-background rounded-lg border border-border/50 text-sm">
                                    {copilotReply}
                                </div>
                            )}
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={copilotQuery}
                                    onChange={(e) => setCopilotQuery(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleSectionCopilot()}
                                    placeholder="e.g., Can you expand on this point?"
                                    className="flex-1 px-3 py-2 bg-background border border-border/50 rounded-lg text-sm"
                                />
                                <Button
                                    size="sm"
                                    onClick={handleSectionCopilot}
                                    disabled={copilotLoading || !copilotQuery.trim()}
                                >
                                    {copilotLoading ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Send className="w-4 h-4" />
                                    )}
                                </Button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

const ContentBlock: React.FC<{ block: any }> = ({ block }) => {
    // Handle kind-based blocks (real oracle/section agent output)
    if (block.kind === 'markdown') {
        return (
            <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {block.text}
            </div>
        );
    }

    if (block.kind === 'highlight') {
        return (
            <div className="bg-primary/10 border border-primary/20 rounded-lg p-3 inline-block min-w-32">
                <div className="text-xs text-muted-foreground">{block.metric}</div>
                <div className="text-2xl font-bold text-primary">{block.value}</div>
                {block.source && (
                    <div className="text-xs text-muted-foreground mt-1 truncate max-w-48">
                        {block.source}
                    </div>
                )}
            </div>
        );
    }

    if (block.kind === 'insight') {
        return (
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
                <div className="font-medium text-sm mb-1">💡 {block.title}</div>
                <div className="text-sm">{block.content}</div>
                {block.data_source && (
                    <div className="text-xs text-muted-foreground mt-1">Source: {block.data_source}</div>
                )}
            </div>
        );
    }

    if (block.kind === 'table') {
        const columns: string[] = block.columns || [];
        const rows: any[][] = block.rows || [];
        if (!columns.length) return null;
        return (
            <div className="overflow-x-auto">
                {block.title && <p className="text-sm font-medium mb-2">{block.title}</p>}
                <table className="w-full text-sm border border-border/50 rounded-lg">
                    <thead className="bg-muted/50">
                        <tr>
                            {columns.map((col, idx) => (
                                <th key={idx} className="px-3 py-2 text-left font-medium">{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, rowIdx) => (
                            <tr key={rowIdx} className="border-t border-border/50">
                                {row.map((cell, cellIdx) => (
                                    <td key={cellIdx} className="px-3 py-2">{cell}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    }

    if (block.kind === 'media' && block.url) {
        return (
            <div className="rounded-lg overflow-hidden border border-border/50">
                <img src={block.url} alt={block.title || 'Media'} className="w-full h-auto" />
                {block.description && (
                    <p className="text-xs text-muted-foreground p-2 bg-muted/50">{block.description}</p>
                )}
            </div>
        );
    }

    if (block.kind === 'citation') {
        // Rendered separately in the citations sidebar — skip inline
        return null;
    }

    // Legacy type-based blocks
    if (block.type === 'text') {
        return <p className="text-sm leading-relaxed">{block.content}</p>;
    }

    if (block.type === 'table' && block.content) {
        return (
            <div className="overflow-x-auto">
                <table className="w-full text-sm border border-border/50 rounded-lg">
                    <thead className="bg-muted/50">
                        <tr>
                            {block.content.columns?.map((col: string, idx: number) => (
                                <th key={idx} className="px-3 py-2 text-left font-medium">{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {block.content.rows?.map((row: any[], rowIdx: number) => (
                            <tr key={rowIdx} className="border-t border-border/50">
                                {row.map((cell, cellIdx) => (
                                    <td key={cellIdx} className="px-3 py-2">{cell}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    }

    if (block.type === 'media' && block.content?.url) {
        return (
            <div className="rounded-lg overflow-hidden border border-border/50">
                <img
                    src={block.content.url}
                    alt={block.content.caption || 'Media'}
                    className="w-full h-auto"
                />
                {block.content.caption && (
                    <p className="text-xs text-muted-foreground p-2 bg-muted/50">
                        {block.content.caption}
                    </p>
                )}
            </div>
        );
    }

    return null;
};

// ─── Live Widget ──────────────────────────────────────────────────────────────

const LiveWidget: React.FC<{ widget: any }> = ({ widget }) => {
    const type: string = widget.type || widget.widget_type || '';
    const config = widget.config || {};

    const [weatherData, setWeatherData] = useState<any>(null);
    const [weatherLoading, setWeatherLoading] = useState(false);
    const [stockPrices, setStockPrices] = useState<Record<string, number>>({});
    const [stockPrev, setStockPrev] = useState<Record<string, number>>({});
    const [chartValues, setChartValues] = useState<number[]>([]);
    const [pollVotes, setPollVotes] = useState<number[]>([]);
    const [pollVoted, setPollVoted] = useState(false);
    const [calcInput, setCalcInput] = useState('');
    const [calcResult, setCalcResult] = useState<string | null>(null);

    useEffect(() => {
        if (type === 'weather') {
            setWeatherLoading(true);
            const lat = config.lat ?? 40.71;
            const lon = config.lon ?? -74.01;
            fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`)
                .then(r => r.json())
                .then(d => { setWeatherData(d.current_weather); setWeatherLoading(false); })
                .catch(() => setWeatherLoading(false));
        } else if (type === 'stock_ticker') {
            const symbols: string[] = config.symbols ?? ['AAPL', 'GOOGL', 'MSFT'];
            const initial: Record<string, number> = {};
            symbols.forEach((s: string) => { initial[s] = Math.round((100 + Math.random() * 400) * 100) / 100; });
            setStockPrices(initial);
            setStockPrev(initial);
            const id = setInterval(() => {
                setStockPrices(prev => {
                    const next: Record<string, number> = {};
                    symbols.forEach((s: string) => {
                        next[s] = Math.round((prev[s] ?? 100) * (1 + (Math.random() - 0.48) * 0.015) * 100) / 100;
                    });
                    setStockPrev(prev);
                    return next;
                });
            }, 4000);
            return () => clearInterval(id);
        } else if (type === 'live_chart') {
            const seed = Array.from({ length: 10 }, () => Math.round(40 + Math.random() * 60));
            setChartValues(seed);
            const id = setInterval(() => {
                setChartValues(prev => [...prev.slice(1), Math.round(40 + Math.random() * 60)]);
            }, (config.interval ?? 5) * 1000);
            return () => clearInterval(id);
        } else if (type === 'poll') {
            const count = (config.options ?? []).length || 3;
            setPollVotes(new Array(count).fill(0));
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [type]);

    const handleCalc = () => {
        try {
            // Safe eval for basic arithmetic only (no exec/no-eval lint expected in prod)
            const sanitised = calcInput.replace(/[^0-9+\-*/().\s]/g, '');
            // eslint-disable-next-line no-new-func
            const val = new Function(`return (${sanitised})`)();
            setCalcResult(String(val));
        } catch { setCalcResult('Error'); }
    };

    const widgetBase = 'border border-border/60 rounded-xl p-4 bg-muted/20';

    if (type === 'weather') {
        const code = weatherData?.weathercode ?? 0;
        const desc = code === 0 ? 'Clear' : code <= 3 ? 'Partly Cloudy' : code <= 48 ? 'Foggy' : code <= 67 ? 'Rainy' : code <= 77 ? 'Snowy' : 'Stormy';
        return (
            <div className={widgetBase}>
                <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                    <CloudSun className="w-3.5 h-3.5" />
                    Live Weather · {config.city || 'Location'}
                </div>
                {weatherLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
                ) : weatherData ? (
                    <div className="flex items-center gap-4">
                        <div className="text-4xl font-bold">{Math.round(weatherData.temperature)}°C</div>
                        <div className="text-sm text-muted-foreground">
                            <div>{desc}</div>
                            <div>Wind {weatherData.windspeed} km/h</div>
                        </div>
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">Unable to fetch weather data.</p>
                )}
            </div>
        );
    }

    if (type === 'stock_ticker') {
        const symbols: string[] = config.symbols ?? ['AAPL', 'GOOGL', 'MSFT'];
        return (
            <div className={widgetBase}>
                <div className="flex items-center gap-2 mb-3 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                    <BarChart2 className="w-3.5 h-3.5" />
                    Live Stock Ticker (simulated)
                </div>
                <div className="flex flex-wrap gap-3">
                    {symbols.map((sym: string) => {
                        const price = stockPrices[sym] ?? 0;
                        const prev = stockPrev[sym] ?? price;
                        const up = price >= prev;
                        return (
                            <div key={sym} className="flex flex-col items-center px-3 py-2 rounded-lg bg-background border border-border/50 min-w-[80px]">
                                <span className="text-xs font-semibold text-muted-foreground">{sym}</span>
                                <span className="text-base font-bold">${price.toFixed(2)}</span>
                                <span className={`text-xs font-medium ${up ? 'text-green-500' : 'text-red-400'}`}>
                                    {up ? '▲' : '▼'} {Math.abs(((price - prev) / (prev || 1)) * 100).toFixed(2)}%
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    }

    if (type === 'live_chart') {
        const maxV = Math.max(...chartValues, 1);
        return (
            <div className={widgetBase}>
                <div className="flex items-center gap-2 mb-3 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                    <Zap className="w-3.5 h-3.5" />
                    {config.title || 'Live Chart'} — updates every {config.interval ?? 5}s
                </div>
                <div className="flex items-end gap-1 h-16">
                    {chartValues.map((v, i) => (
                        <div
                            key={i}
                            className="flex-1 rounded-t bg-primary/60 transition-all duration-500"
                            style={{ height: `${(v / maxV) * 100}%` }}
                            title={String(v)}
                        />
                    ))}
                </div>
            </div>
        );
    }

    if (type === 'poll') {
        const options: string[] = config.options ?? ['Yes', 'No', 'Maybe'];
        const total = pollVotes.reduce((a, b) => a + b, 0);
        return (
            <div className={widgetBase}>
                <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                    <Vote className="w-3.5 h-3.5" />
                    Poll
                </div>
                <p className="text-sm font-medium mb-3">{config.question || 'What do you think?'}</p>
                <div className="space-y-2">
                    {options.map((opt: string, i: number) => {
                        const pct = total > 0 ? Math.round((pollVotes[i] / total) * 100) : 0;
                        return (
                            <button
                                key={i}
                                disabled={pollVoted}
                                onClick={() => {
                                    if (!pollVoted) {
                                        setPollVotes(v => v.map((c, idx) => idx === i ? c + 1 : c));
                                        setPollVoted(true);
                                    }
                                }}
                                className="w-full text-left"
                            >
                                <div className="flex items-center justify-between text-sm mb-0.5">
                                    <span>{opt}</span>
                                    {pollVoted && <span className="text-xs text-muted-foreground">{pct}%</span>}
                                </div>
                                <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                                    <div
                                        className="h-full bg-primary/70 rounded-full transition-all duration-700"
                                        style={{ width: pollVoted ? `${pct}%` : '0%' }}
                                    />
                                </div>
                            </button>
                        );
                    })}
                </div>
                {pollVoted && <p className="text-xs text-muted-foreground mt-2">{total} vote{total !== 1 ? 's' : ''} total</p>}
            </div>
        );
    }

    if (type === 'calculator') {
        return (
            <div className={widgetBase}>
                <div className="flex items-center gap-2 mb-3 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                    <Calculator className="w-3.5 h-3.5" />
                    Calculator
                </div>
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={calcInput}
                        onChange={e => { setCalcInput(e.target.value); setCalcResult(null); }}
                        onKeyDown={e => e.key === 'Enter' && handleCalc()}
                        placeholder="e.g. (12 + 8) * 3"
                        className="flex-1 px-3 py-1.5 text-sm bg-background border border-border rounded-lg outline-none focus:ring-2 focus:ring-primary/40"
                    />
                    <Button size="sm" variant="outline" onClick={handleCalc}>=</Button>
                </div>
                {calcResult !== null && (
                    <p className="mt-2 text-lg font-bold">
                        {calcResult === 'Error' ? <span className="text-red-400">Error</span> : calcResult}
                    </p>
                )}
            </div>
        );
    }

    return null;
};

// ─── Chart Block ───────────────────────────────────────────────────────────────

const ChartBlock: React.FC<{ chart: any }> = ({ chart }) => {
    const labels: string[] = chart.chart_data?.labels || chart.chart_data?.datasets?.[0]?.data?.map((_: any, i: number) => `Item ${i + 1}`) || [];
    const values: number[] = chart.chart_data?.datasets?.[0]?.data || [];
    const maxVal = Math.max(...values.filter((v): v is number => typeof v === 'number'), 1);

    if (chart.type === 'bar' && labels.length && values.length) {
        return (
            <div className="border border-border/50 rounded-lg p-4">
                <p className="text-sm font-medium mb-3">📊 {chart.title}</p>
                <div className="space-y-2">
                    {labels.map((label, idx) => (
                        <div key={idx} className="flex items-center gap-3 text-sm">
                            <span className="w-28 text-right text-muted-foreground truncate text-xs shrink-0">{label}</span>
                            <div className="flex-1 bg-muted/50 rounded-full h-5 overflow-hidden">
                                <div
                                    className="h-full bg-primary/70 rounded-full transition-all"
                                    style={{ width: `${((values[idx] ?? 0) / maxVal) * 100}%` }}
                                />
                            </div>
                            <span className="text-xs text-muted-foreground w-12 text-left">{values[idx]}</span>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    if (chart.type === 'pie' && labels.length && values.length) {
        const total = values.reduce((a: number, b: number) => a + (b || 0), 0);
        const colors = ['bg-blue-500', 'bg-red-400', 'bg-yellow-400', 'bg-green-500', 'bg-purple-500', 'bg-orange-400'];
        return (
            <div className="border border-border/50 rounded-lg p-4">
                <p className="text-sm font-medium mb-3">🥧 {chart.title}</p>
                <div className="space-y-2">
                    {labels.map((label, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm">
                            <div className={`w-3 h-3 rounded-full shrink-0 ${colors[idx % colors.length]}`} />
                            <span className="flex-1 text-xs">{label}</span>
                            <span className="text-xs text-muted-foreground">
                                {total > 0 ? `${((values[idx] / total) * 100).toFixed(1)}%` : '-'}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    // Fallback for other chart types
    return (
        <div className="border border-border/50 rounded-lg p-4 bg-muted/20">
            <p className="text-sm font-medium">📊 {chart.title}</p>
            <p className="text-xs text-muted-foreground mt-1">{chart.type?.toUpperCase()} chart — {labels.length} data points</p>
        </div>
    );
};

// ─── Client-side export helpers ─────────────────────────────────────────────

function generateMarkdown(page: PageData): string {
    const lines: string[] = [
        `# ${page.query}`,
        '',
        `*Template: ${page.template} · Generated: ${page.metadata.created_at}*`,
        '',
    ];
    for (const section of page.sections) {
        lines.push(`## ${section.title}`, '');
        for (const block of section.blocks) {
            if (block.kind === 'markdown' && block.text) lines.push(block.text, '');
            else if (block.kind === 'highlight') lines.push(`**${block.metric}:** ${block.value}`, '');
            else if (block.kind === 'insight') lines.push(`> 💡 **${block.title}**\n> ${block.content}`, '');
            else if (block.type === 'text' && block.content) lines.push(block.content, '');
        }
    }
    if (page.citations.length) {
        lines.push('## References', '');
        page.citations.forEach((c, i) => lines.push(`[${i + 1}] [${c.title || c.id}](${c.url})`, ''));
    }
    return lines.join('\n');
}

function generateHtml(page: PageData): string {
    const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    let body = `<h1>${escape(page.query)}</h1>\n<p><em>Template: ${escape(page.template)}</em></p>\n`;
    for (const section of page.sections) {
        body += `<h2>${escape(section.title)}</h2>\n`;
        for (const block of section.blocks) {
            if (block.kind === 'markdown' && block.text)
                body += `<p>${escape(block.text)}</p>\n`;
            else if (block.kind === 'highlight')
                body += `<p><strong>${escape(block.metric ?? '')}:</strong> ${escape(String(block.value ?? ''))}</p>\n`;
            else if (block.kind === 'insight')
                body += `<blockquote><strong>${escape(block.title ?? '')}</strong><br>${escape(block.content ?? '')}</blockquote>\n`;
            else if (block.type === 'text' && block.content)
                body += `<p>${escape(block.content)}</p>\n`;
        }
    }
    if (page.citations.length) {
        body += '<h2>References</h2>\n<ol>\n';
        page.citations.forEach(c => { body += `<li><a href="${escape(c.url)}">${escape(c.title || c.id)}</a></li>\n`; });
        body += '</ol>\n';
    }
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escape(page.query)}</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:auto;padding:2rem;line-height:1.7}h1{font-size:2rem;margin-bottom:.5rem}h2{font-size:1.3rem;margin-top:2rem;border-bottom:1px solid #eee;padding-bottom:.25rem}blockquote{border-left:4px solid #6366f1;margin:1rem 0;padding:.75rem 1rem;background:#f9f9ff;border-radius:4px}a{color:#6366f1}</style>
</head>
<body>
${body}</body>
</html>`;
}
