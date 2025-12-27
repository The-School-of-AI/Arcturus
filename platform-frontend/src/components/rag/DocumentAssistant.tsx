import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Trash2, Quote, ScrollText, MessageSquare, X, ChevronDown, ChevronUp } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MessageContent: React.FC<{ content: string, role: 'user' | 'assistant' | 'system' }> = ({ content, role }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    if (role === 'user') {
        return (
            <div className="text-sm leading-relaxed">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
        );
    }

    if (typeof content !== 'string') {
        return <div className="text-xs text-muted-foreground italic">Invalid message content</div>;
    }

    const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
    const thinking = thinkMatch ? thinkMatch[1].trim() : null;
    const mainAnswer = content.replace(/<think>[\s\S]*?<\/think>/, '').trim();

    return (
        <div className="space-y-3">
            {thinking && (
                <div className="bg-black/20 border border-border/50 rounded-xl overflow-hidden mb-2">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="w-full flex items-center justify-between px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-primary/60 hover:bg-white/5 transition-colors"
                    >
                        <div className="flex items-center gap-2">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-40"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary/60"></span>
                            </span>
                            Thinking Process
                        </div>
                        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                    {isExpanded && (
                        <div className="px-4 py-3 text-[11px] text-foreground/50 border-t border-border/50 leading-relaxed bg-black/40 italic">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{thinking}</ReactMarkdown>
                        </div>
                    )}
                </div>
            )}
            <div className="text-sm leading-relaxed">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{mainAnswer || (thinking ? "" : content)}</ReactMarkdown>
            </div>
        </div>
    );
};

export const DocumentAssistant: React.FC = () => {
    const activeDocumentId = useAppStore(state => state.activeDocumentId);
    const openDocuments = useAppStore(state => state.openDocuments);
    const addMessageToDocChat = useAppStore(state => state.addMessageToDocChat);
    const selectedContexts = useAppStore(state => state.selectedContexts);
    const removeSelectedContext = useAppStore(state => state.removeSelectedContext);
    const clearSelectedContexts = useAppStore(state => state.clearSelectedContexts);
    const [inputValue, setInputValue] = useState('');
    const [isThinking, setIsThinking] = useState(false);
    const [pastedImage, setPastedImage] = useState<string | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);
    const history = activeDoc?.chatHistory || [];

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, isThinking]);

    const handlePaste = (e: React.ClipboardEvent) => {
        const items = e.clipboardData.items;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                if (blob) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        setPastedImage(event.target?.result as string);
                    };
                    reader.readAsDataURL(blob);
                }
            }
        }
    };

    const handleSend = async () => {
        if ((!inputValue.trim() && !pastedImage) || !activeDoc) return;

        // Combine all selected contexts
        const contextString = selectedContexts.length > 0
            ? `Context extracts from document:\n${selectedContexts.map(c => `> ${c}`).join('\n\n')}\n\n`
            : '';

        const userMsgId = Date.now().toString();
        const userMsg = {
            id: userMsgId,
            role: 'user' as const,
            content: inputValue + (pastedImage ? "\n\n[Pasted Image]" : ""),
            timestamp: Date.now()
        };

        const fullMessage = contextString + `User Question: ${inputValue}`;
        const currentPastedImage = pastedImage;

        addMessageToDocChat(activeDoc.id, userMsg);
        setInputValue('');
        setPastedImage(null);
        clearSelectedContexts();
        setIsThinking(true);

        const botMsgId = (Date.now() + 1).toString();
        const botMsg = {
            id: botMsgId,
            role: 'assistant' as const,
            content: '',
            timestamp: Date.now()
        };
        addMessageToDocChat(activeDoc.id, botMsg);

        try {
            const response = await fetch('http://localhost:8000/rag/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    docId: activeDoc.id,
                    query: fullMessage,
                    history: history,
                    image: currentPastedImage
                })
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedContent = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.content) {
                                accumulatedContent += data.content;
                                // Update the bot message in real-time
                                const updatedBotMsg = { ...botMsg, content: accumulatedContent };
                                addMessageToDocChat(activeDoc.id, updatedBotMsg);
                            } else if (data.error) {
                                console.error("Streaming error:", data.error);
                            }
                        } catch (e) {
                            // Part of a JSON chunk, wait for next
                        }
                    }
                }
            }
        } catch (e) {
            console.error("Failed to ask document:", e);
        } finally {
            setIsThinking(false);
        }
    };

    if (!activeDoc) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center bg-background">
                <ScrollText className="w-12 h-12 mb-4 opacity-20" />
                <h3 className="font-semibold text-foreground mb-2">Document Assistant</h3>
                <p className="text-sm">Select a document from the library to start an interactive deep-dive.</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background">
            {/* Header */}
            <div className="p-4 border-b border-border bg-card/95 sticky top-0 z-10 flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <MessageSquare className="w-4 h-4 text-primary" />
                        <h3 className="font-bold text-xs uppercase tracking-widest text-foreground">Talk to Document</h3>
                    </div>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">{activeDoc.title}</p>
                </div>
            </div>

            {/* Chat History */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {history.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center opacity-50 space-y-2">
                        <Bot className="w-8 h-8" />
                        <p className="text-xs">Ask anything about this document.<br />Selected text from the viewer will be added as context automatically.</p>
                    </div>
                )}

                {history.map((msg) => (
                    <div key={msg.id} className={cn(
                        "flex gap-3",
                        msg.role === 'user' ? "flex-row-reverse" : "flex-row"
                    )}>
                        <div className={cn(
                            "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-1",
                            msg.role === 'user' ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
                        )}>
                            {msg.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                        </div>
                        <div className={cn(
                            "max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed",
                            msg.role === 'user'
                                ? "bg-primary/20 text-foreground border border-primary/20 rounded-tr-none"
                                : "bg-muted text-foreground/90 border border-border/50 rounded-tl-none px-0 py-0 overflow-hidden" // Special padding for assistant to allow full-width thought blocks
                        )}>
                            <div className={cn(msg.role === 'assistant' ? "p-4" : "")}>
                                <MessageContent content={msg.content} role={msg.role} />
                            </div>
                        </div>
                    </div>
                ))}

                {isThinking && (
                    <div className="flex gap-3 animate-pulse">
                        <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center flex-shrink-0 mt-1">
                            <Bot className="w-3 h-3" />
                        </div>
                        <div className="bg-muted border border-border/50 rounded-2xl rounded-tl-none px-4 py-2">
                            <div className="flex gap-1">
                                <span className="w-1 h-1 rounded-full bg-foreground/30 animate-bounce" style={{ animationDelay: '0ms' }} />
                                <span className="w-1 h-1 rounded-full bg-foreground/30 animate-bounce" style={{ animationDelay: '150ms' }} />
                                <span className="w-1 h-1 rounded-full bg-foreground/30 animate-bounce" style={{ animationDelay: '300ms' }} />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Selection Context Indicator - Pills View */}
            {selectedContexts.length > 0 && (
                <div className="px-4 py-2 bg-black/40 border-t border-border space-y-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-primary/60">
                            <Quote className="w-2.5 h-2.5" />
                            Active Context ({selectedContexts.length})
                        </div>
                        <button
                            onClick={clearSelectedContexts}
                            className="text-[9px] font-bold text-muted-foreground hover:text-foreground transition-colors"
                        >
                            Clear All
                        </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto no-scrollbar pb-1">
                        {selectedContexts.map((ctx, idx) => (
                            <div
                                key={idx}
                                className="group flex items-center gap-2 bg-charcoal-800 border border-border/50 rounded-full pl-3 pr-1 py-1 max-w-full animate-in zoom-in-95 duration-200"
                            >
                                <span className="text-[10px] text-foreground/90 truncate flex-1 min-w-0 font-medium">
                                    {ctx.length > 50 ? `${ctx.substring(0, 50)}...` : ctx}
                                </span>
                                <button
                                    onClick={() => removeSelectedContext(idx)}
                                    className="p-1 rounded-full hover:bg-white/10 text-muted-foreground hover:text-red-400 transition-all opacity-60 group-hover:opacity-100"
                                >
                                    <X className="w-2.5 h-2.5" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Input Area */}
            <div className="p-4 border-t border-border bg-card space-y-3">
                {/* Image Preview */}
                {pastedImage && (
                    <div className="relative w-24 h-24 group animate-in zoom-in-95 duration-200">
                        <img
                            src={pastedImage}
                            alt="Pasted content"
                            className="w-full h-full object-cover rounded-lg border border-primary/30 shadow-lg shadow-primary/10"
                        />
                        <button
                            onClick={() => setPastedImage(null)}
                            className="absolute -top-2 -right-2 p-1 bg-charcoal-800 border border-border rounded-full hover:bg-red-500 hover:text-foreground transition-all shadow-xl"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                )}

                <div className="relative group">
                    <input
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !isThinking && handleSend()}
                        onPaste={handlePaste}
                        placeholder="Type or paste image..."
                        className="w-full bg-black/40 border border-border rounded-xl px-4 py-3 pr-12 text-sm text-foreground focus:outline-none focus:border-primary/50 transition-all placeholder:text-muted-foreground/50"
                        disabled={isThinking}
                    />
                    <button
                        onClick={handleSend}
                        disabled={(!inputValue.trim() && !pastedImage) || isThinking}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-primary hover:bg-primary/10 rounded-lg transition-all disabled:opacity-30 disabled:grayscale"
                    >
                        <Send className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
};
