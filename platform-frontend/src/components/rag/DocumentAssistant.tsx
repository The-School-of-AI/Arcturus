import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Trash2, Quote, ScrollText, MessageSquare, X, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '@/lib/api';

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

    // Handle partial tags during streaming using check for end of string or closing tag
    const thinkMatch = content.match(/<think>([\s\S]*?)(?:<\/think>|$)/);
    const thinking = thinkMatch ? thinkMatch[1].trim() : null;
    const mainAnswer = content.replace(/<think>([\s\S]*?)(?:<\/think>|$)/, '').trim();

    return (
        <div className="space-y-3">
            {thinking && (
                <div className="bg-muted border border-border/50 rounded-xl overflow-hidden mb-2">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="w-full flex items-center justify-between px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-primary/80 hover:bg-background/50 transition-colors"
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
                        <div className="px-4 py-3 text-[11px] text-muted-foreground border-t border-border/50 leading-relaxed bg-background/50 italic">
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
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const activeDoc = openDocuments.find(d => d.id === activeDocumentId);
    const history = activeDoc?.chatHistory || [];

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, isThinking]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

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
        let contextString = selectedContexts.length > 0
            ? `Context extracts from document:\n${selectedContexts.map(c => `> ${c}`).join('\n\n')}\n\n`
            : '';

        // SPECIAL CASE: For Summarize/Key Takeaways, fetch FULL chunks
        if (inputValue.includes("Summarize") || inputValue.includes("Key Takeaways") || inputValue.includes("takeaways")) {
            try {
                const res = await fetch(`${API_BASE}/rag/document_chunks?path=${encodeURIComponent(activeDoc.id)}`);
                const data = await res.json();
                if (data.status === 'success' && data.markdown) {
                    // Limit context to ~30k chars to avoid token limits (adjust based on model)
                    const chunks = data.markdown.slice(0, 30000);
                    contextString += `\n\nFULL DOCUMENT CONTENT (Truncated to first 30k chars):\n${chunks}\n\n`;
                }
            } catch (e) {
                console.error("Failed to fetch full context", e);
            }
        }

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
            const response = await fetch(`${API_BASE}/rag/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    docId: activeDoc.id,
                    query: fullMessage,
                    history: history, // Send full history including context
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
                                // Update the SPECIFIC bot message using its ID
                                useAppStore.getState().updateMessageContent(activeDoc.id, botMsgId, accumulatedContent);
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
            useAppStore.getState().updateMessageContent(activeDoc.id, botMsgId, "⚠️ Error communicating with AI. Please try again.");
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
                        <Sparkles className="w-4 h-4 text-purple-400" />
                        <h3 className="font-bold text-xs uppercase tracking-widest text-foreground">Insights</h3>
                    </div>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">{activeDoc.title}</p>
                </div>
            </div>

            {/* Chat History */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {history.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4 py-8">
                        <div className="opacity-50 space-y-2">
                            <Bot className="w-8 h-8 mx-auto" />
                            <p className="text-xs">Ask anything about this document.<br />Selected text from the viewer will be added as context automatically.</p>
                        </div>

                        {/* Quick Actions */}
                        <div className="flex flex-col gap-2 w-full max-w-xs mt-4">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Quick Actions</p>
                            <button
                                onClick={() => {
                                    setInputValue('Summarize this document in 3-5 concise bullet points');
                                    setTimeout(handleSend, 100);
                                }}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 hover:bg-muted rounded-lg text-sm text-foreground transition-all border border-border/50 hover:border-primary/30"
                            >
                                <ScrollText className="w-4 h-4 text-primary" />
                                Summarize Document
                            </button>
                            <button
                                onClick={() => {
                                    setInputValue('Extract the key takeaways and insights from this document. Focus on actionable points.');
                                    setTimeout(handleSend, 100);
                                }}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 hover:bg-muted rounded-lg text-sm text-foreground transition-all border border-border/50 hover:border-primary/30"
                            >
                                <Quote className="w-4 h-4 text-primary" />
                                Key Takeaways
                            </button>
                        </div>
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
                        <div
                            className={cn(
                                "p-3 rounded-2xl max-w-[85%] text-xs leading-relaxed shadow-sm relative group",
                                msg.role === 'user'
                                    ? "bg-primary text-primary-foreground rounded-tr-none ml-auto"
                                    : "bg-muted text-foreground rounded-tl-none border border-border"
                            )}
                        >
                            <div className={cn(msg.role === 'assistant' ? "" : "")}> {/* Removed p-4 for assistant, now handled by outer div */}
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

            {/* Input Area */}
            <div className="p-4 bg-card border-t border-border">
                {/* Image Preview */}
                {pastedImage && (
                    <div className="relative mb-2 inline-block">
                        <img src={pastedImage} alt="Pasted" className="h-20 rounded-md border border-border" />
                        <button
                            onClick={() => setPastedImage(null)}
                            className="absolute -top-2 -right-2 p-1 bg-destructive text-destructive-foreground rounded-full hover:bg-destructive/90"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                )}

                {/* Selected Context Pills */}
                {selectedContexts.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                        {selectedContexts.map((ctx, i) => (
                            <div key={i} className="flex items-center gap-1 px-2 py-1 bg-purple-500/20 text-purple-400 text-[10px] rounded max-w-full">
                                <span className="truncate max-w-[200px]"><Quote className="w-3 h-3 inline mr-1" />{ctx.substring(0, 30)}...</span>
                                <button onClick={() => removeSelectedContext(i)} className="hover:text-purple-300"><X className="w-3 h-3" /></button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="flex gap-2 items-end">
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onPaste={handlePaste}
                            placeholder={selectedContexts.length > 0 ? "Ask about selected text..." : "Ask a question..."}
                            className="w-full bg-muted/50 text-foreground placeholder:text-muted-foreground border border-input rounded-xl px-3 py-2 pr-10 text-xs focus:outline-none focus:ring-1 focus:ring-ring resize-none min-h-[40px] max-h-[120px]"
                            style={{
                                height: 'auto',
                                overflow: inputValue.split('\n').length > 3 ? 'auto' : 'hidden'
                            }}
                        />
                    </div>
                    <button
                        onClick={handleSend}
                        disabled={!inputValue.trim() && !pastedImage}
                        className={cn(
                            "p-2.5 rounded-xl transition-all",
                            inputValue.trim() || pastedImage
                                ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm"
                                : "bg-muted text-muted-foreground hover:bg-muted/80"
                        )}
                    >
                        <Send className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
};
