import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Quote, ScrollText, X, ChevronDown, ChevronUp, Sparkles, FileText, Globe } from 'lucide-react';
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

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
}

export const NewsInspector: React.FC = () => {
    const {
        activeNewsTab,
        newsTabs,
        selectedContexts,
        removeSelectedContext,
        clearSelectedContexts,
        setShowNewsChatPanel
    } = useAppStore();

    const [inputValue, setInputValue] = useState('');
    const [isThinking, setIsThinking] = useState(false);
    const [history, setHistory] = useState<ChatMessage[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Get the current article URL (if any tab is open)
    const activeUrl = activeNewsTab || (newsTabs.length > 0 ? newsTabs[0] : null);
    const activeTitle = activeUrl ? new URL(activeUrl).hostname : null;

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, isThinking]);

    // Clear history when switching articles
    useEffect(() => {
        setHistory([]);
    }, [activeUrl]);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleSend = async () => {
        if (!inputValue.trim() || !activeUrl) return;

        let contextString = selectedContexts.length > 0
            ? `Context extracts from article:\n${selectedContexts.map(c => `> ${c}`).join('\n\n')}\n\n`
            : '';

        const userMsgId = Date.now().toString();
        const userMsg: ChatMessage = {
            id: userMsgId,
            role: 'user',
            content: inputValue,
            timestamp: Date.now()
        };

        const fullMessage = contextString + `User Question: ${inputValue}`;

        setHistory(prev => [...prev, userMsg]);
        setInputValue('');
        clearSelectedContexts();
        setIsThinking(true);

        const botMsgId = (Date.now() + 1).toString();
        const botMsg: ChatMessage = {
            id: botMsgId,
            role: 'assistant',
            content: '',
            timestamp: Date.now()
        };
        setHistory(prev => [...prev, botMsg]);

        try {
            // First, fetch the article content for context
            const articleRes = await fetch(`${API_BASE}/news/article?url=${encodeURIComponent(activeUrl)}`);
            const articleData = await articleRes.json();

            let articleContext = '';
            if (articleData.status === 'success' && articleData.content) {
                // Limit to first 15k characters
                articleContext = `\n\nARTICLE CONTENT:\n${articleData.content.slice(0, 15000)}\n\n`;
            }

            // Use the RAG ask endpoint for answering
            const response = await fetch(`${API_BASE}/rag/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    docId: activeUrl,
                    query: articleContext + fullMessage,
                    history: history
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
                                setHistory(prev => prev.map(m =>
                                    m.id === botMsgId ? { ...m, content: accumulatedContent } : m
                                ));
                            }
                        } catch (e) {
                            // Partial JSON
                        }
                    }
                }
            }
        } catch (e) {
            console.error("Failed to ask about article:", e);
            setHistory(prev => prev.map(m =>
                m.id === botMsgId ? { ...m, content: "⚠️ Error communicating with AI. Please try again." } : m
            ));
        } finally {
            setIsThinking(false);
        }
    };

    if (!activeUrl) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center bg-background">
                <Globe className="w-12 h-12 mb-4 opacity-20" />
                <h3 className="font-semibold text-foreground mb-2">News Assistant</h3>
                <p className="text-sm">Select an article from the feed to ask questions or explore insights.</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background">
            {/* Header */}
            <div className="p-4 border-b border-border bg-card/95 sticky top-0 z-10 flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Sparkles className="w-4 h-4 text-cyan-400" />
                        <h3 className="font-bold text-xs uppercase tracking-widest text-foreground">Insights</h3>
                    </div>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">{activeTitle}</p>
                </div>
                <button
                    onClick={() => setShowNewsChatPanel(false)}
                    className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground bg-muted hover:bg-muted/80 rounded-md transition-colors"
                >
                    Exit
                </button>
            </div>

            {/* Chat History */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {history.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4 py-8">
                        <div className="opacity-50 space-y-2">
                            <Bot className="w-8 h-8 mx-auto" />
                            <p className="text-xs">Ask anything about this article.<br />Selected text from the reader will be added as context automatically.</p>
                        </div>

                        {/* Quick Actions */}
                        <div className="flex flex-col gap-2 w-full max-w-xs mt-4">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Quick Actions</p>
                            <button
                                onClick={() => {
                                    setInputValue('Summarize this article in 3-5 concise bullet points');
                                    setTimeout(handleSend, 100);
                                }}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 hover:bg-muted rounded-lg text-sm text-foreground transition-all border border-border/50 hover:border-primary/30"
                            >
                                <ScrollText className="w-4 h-4 text-cyan-400" />
                                Summarize Article
                            </button>
                            <button
                                onClick={() => {
                                    setInputValue('Extract the key takeaways and insights from this article. Focus on actionable points.');
                                    setTimeout(handleSend, 100);
                                }}
                                disabled={isThinking}
                                className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 hover:bg-muted rounded-lg text-sm text-foreground transition-all border border-border/50 hover:border-primary/30"
                            >
                                <Quote className="w-4 h-4 text-cyan-400" />
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
                            <MessageContent content={msg.content} role={msg.role} />
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
                {/* Selected Context Pills */}
                {selectedContexts.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                        {selectedContexts.map((ctx, i) => (
                            <div key={i} className="flex items-center gap-1 px-2 py-1 bg-cyan-500/20 text-cyan-400 text-[10px] rounded max-w-full">
                                <span className="truncate max-w-[200px]"><Quote className="w-3 h-3 inline mr-1" />{(typeof ctx === 'string' ? ctx : ctx.text).substring(0, 30)}...</span>
                                <button onClick={() => removeSelectedContext(i)} className="hover:text-cyan-300"><X className="w-3 h-3" /></button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="flex gap-2 items-end">
                    <div className="flex-1 relative">
                        <textarea
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={handleKeyDown}
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
                        disabled={!inputValue.trim()}
                        className={cn(
                            "p-2.5 rounded-xl transition-all",
                            inputValue.trim()
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
