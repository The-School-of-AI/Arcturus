import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Trash2, Quote, ScrollText, MessageSquare, X, ChevronDown, ChevronUp, Sparkles, History, Plus, Clock, Cpu, ChevronRight } from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '@/lib/api';

const MessageContent: React.FC<{ content: string, role: 'user' | 'assistant' | 'system' }> = ({ content, role }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    if (role === 'user') {
        return (
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                {content}
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

    // Calculate approximate tokens (4 chars/token)
    const tokenCount = thinking ? Math.max(1, Math.round(thinking.length / 4)) : 0;

    return (
        <div className="space-y-1 min-w-0">
            {thinking && (
                <div className="mb-2">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground/60 hover:text-foreground transition-colors select-none py-1"
                    >
                        <ChevronRight className={cn("w-3.5 h-3.5 transition-transform", isExpanded ? "rotate-90" : "")} />
                        <span className="font-medium">Thought for ~{tokenCount} tokens</span>
                    </button>
                    {isExpanded && (
                        <div className="mt-2 pl-4 border-l-2 border-primary/20 text-muted-foreground text-xs leading-relaxed">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{thinking}</ReactMarkdown>
                        </div>
                    )}
                </div>
            )}
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground/90">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{mainAnswer || (thinking ? "" : content)}</ReactMarkdown>
            </div>
        </div>
    );
};

export const DocumentAssistant: React.FC = () => {
    const activeDocumentId = useAppStore(state => state.ragActiveDocumentId);
    const openDocuments = useAppStore(state => state.ragOpenDocuments);

    // Add IDE store access
    const ideActiveDocumentId = useAppStore(state => state.ideActiveDocumentId);
    const ideOpenDocuments = useAppStore(state => state.ideOpenDocuments);

    const addMessageToDocChat = useAppStore(state => state.addMessageToDocChat);
    const selectedContexts = useAppStore(state => state.selectedContexts);
    const removeSelectedContext = useAppStore(state => state.removeSelectedContext);
    const clearSelectedContexts = useAppStore(state => state.clearSelectedContexts);

    // Chat Session Store Hooks
    const chatSessions = useAppStore(state => state.chatSessions);
    const fetchChatSessions = useAppStore(state => state.fetchChatSessions);
    const loadChatSession = useAppStore(state => state.loadChatSession);
    const createNewChatSession = useAppStore(state => state.createNewChatSession);
    const activeChatSessionId = useAppStore(state => state.activeChatSessionId);

    const [inputValue, setInputValue] = useState('');
    const [isThinking, setIsThinking] = useState(false);
    const [pastedImage, setPastedImage] = useState<string | null>(null);
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);
    const [selectedModel, setSelectedModel] = useState('qwen3-vl:8b');
    const scrollRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const isUserScrolledUp = useRef(false);

    // Determine active document from either RAG or IDE
    const sidebarTab = useAppStore(state => state.sidebarTab);
    const activeDoc = (sidebarTab === 'ide' && ideActiveDocumentId)
        ? ideOpenDocuments?.find(d => d.id === ideActiveDocumentId)
        : openDocuments.find(d => d.id === activeDocumentId);

    // Fetch sessions on doc change
    useEffect(() => {
        if (activeDoc) {
            const type = (sidebarTab === 'ide' && ideActiveDocumentId) ? 'ide' : 'rag';
            fetchChatSessions(type, activeDoc.id);
        }
    }, [activeDoc?.id, sidebarTab, ideActiveDocumentId]);

    const history = activeDoc?.chatHistory || [];

    // Smart Scroll Logic
    const handleScroll = () => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            // If user is near bottom (within 50px), they are NOT scrolled up
            isUserScrolledUp.current = scrollHeight - scrollTop - clientHeight > 50;
        }
    };

    useEffect(() => {
        if (scrollRef.current && !isUserScrolledUp.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, isThinking]); // Auto-scroll only if not scrolled up

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
        // Reset scroll lock
        isUserScrolledUp.current = false;

        const botMsgId = (Date.now() + 1).toString();
        const botMsg = {
            id: botMsgId,
            role: 'assistant' as const,
            content: '',
            timestamp: Date.now()
        };

        try {
            const response = await fetch(`${API_BASE}/rag/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    docId: activeDoc.id,
                    query: fullMessage,
                    history: history, // Send full history including context
                    image: currentPastedImage,
                    model: selectedModel // Send selected model
                })
            });

            if (!response.body) throw new Error("No response body");

            // Stop thinking animation and add the empty bot message ONLY when we're ready to stream
            setIsThinking(false);
            addMessageToDocChat(activeDoc.id, botMsg);

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
            setIsThinking(false);
            // If the message wasn't added yet (error during fetch init), add it with error
            // We can check if it exists in list, or just check our local flow. 
            // Simpler: just add a new error message if we failed early.
            // But to be cleaner, let's assume if we are here and isThinking was true, we probably haven't added it or we failed mid-stream.
            // Actually simpler: if we fail, we MUST show something.
            // Let's rely on checking if the message exists in the store? No, that's async/complex.
            // Let's use a flag.
            addMessageToDocChat(activeDoc.id, {
                ...botMsg,
                content: "⚠️ Error communicating with AI. Please try again."
            });
        } finally {
            setIsThinking(false);
        }
    };

    if (!activeDoc) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 bg-white dark:bg-card text-center space-y-4">
                <div className="p-4 rounded-full bg-slate-100 dark:bg-white/5">
                    <ScrollText className="w-8 h-8 text-muted-foreground opacity-20" />
                </div>
                <div className="space-y-1">
                    <h3 className="font-bold text-foreground">Document Assistant</h3>
                    <p className="text-xs text-muted-foreground">Select a document from the library to start an interactive deep-dive.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-white dark:bg-card">
            {/* Header: Minimal */}
            <div className="px-4 py-3 border-b border-border bg-white/95 dark:bg-card/95 backdrop-blur z-10 flex items-center justify-between">
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className="bg-primary/10 p-1.5 rounded-md">
                        <Sparkles className="w-3.5 h-3.5 text-primary" />
                    </div>
                    <div className="flex flex-col min-w-0">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Chat</span>
                        <span className="text-xs font-medium truncate text-foreground">{activeDoc.title}</span>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={() => {
                            const type = (sidebarTab === 'ide' && ideActiveDocumentId) ? 'ide' : 'rag';
                            if (activeDoc) createNewChatSession(type, activeDoc.id);
                        }}
                        className="p-2 hover:bg-muted rounded-md text-muted-foreground hover:text-foreground transition-colors"
                        title="New Chat"
                    >
                        <Plus className="w-4 h-4" />
                    </button>

                    <div className="relative">
                        <button
                            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
                            className={cn(
                                "p-2 hover:bg-muted rounded-md transition-colors",
                                isHistoryOpen ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground"
                            )}
                            title="Chat History"
                        >
                            <History className="w-4 h-4" />
                        </button>

                        {isHistoryOpen && (
                            <div className="absolute top-full right-0 mt-2 w-64 bg-background border border-border shadow-xl rounded-lg z-50 p-2 max-h-60 overflow-y-auto">
                                <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest px-2 py-1 mb-1">Previous Chats</p>
                                {chatSessions.length === 0 ? (
                                    <p className="text-xs text-muted-foreground px-2 py-4 text-center italic">No history yet</p>
                                ) : (
                                    chatSessions.map(session => (
                                        <button
                                            key={session.id}
                                            onClick={() => {
                                                const type = (sidebarTab === 'ide' && ideActiveDocumentId) ? 'ide' : 'rag';
                                                if (activeDoc) loadChatSession(session.id, type, activeDoc.id);
                                                setIsHistoryOpen(false);
                                            }}
                                            className={cn(
                                                "w-full text-left px-2 py-2 rounded-md hover:bg-muted transition-colors text-xs mb-1 flex items-center justify-between group",
                                                activeChatSessionId === session.id ? "bg-muted" : ""
                                            )}
                                        >
                                            <div className="truncate flex-1 pr-2">
                                                <span className="block truncate font-medium">{session.title}</span>
                                                <span className="block text-[9px] text-muted-foreground flex items-center gap-1 mt-0.5">
                                                    <Clock className="w-2 h-2" />
                                                    {new Date(session.updated_at * 1000).toLocaleDateString()}
                                                </span>
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        )}
                    </div>

                    <div className="w-px h-4 bg-border mx-1" />

                    <button
                        onClick={() => useAppStore.getState().clearSelection()}
                        className="p-2 hover:bg-destructive/10 rounded-md text-muted-foreground hover:text-destructive transition-colors"
                        title="Close Panel"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Chat History */}
            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
            >
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
                        "flex flex-col w-full mb-6", // Added mb-6 for better spacing between turns
                        msg.role === 'user' ? "items-end" : "items-start"
                    )}>
                        {/* Message Header (Role Name) - Optional, maybe just for Bot */}
                        {msg.role === 'assistant' && (
                            <div className="flex items-center gap-2 mb-1.5 px-1 opacity-60">
                                <Bot className="w-3 h-3" />
                                <span className="text-[10px] font-bold uppercase tracking-widest">Assistant</span>
                            </div>
                        )}

                        <div
                            className={cn(
                                "max-w-full min-w-0 overflow-hidden",
                                msg.role === 'user' ? "max-w-[85%]" : "w-full" // User gets bubble limit, Bot gets full width
                            )}
                        >
                            <div className={cn(
                                "text-sm",
                                msg.role === 'user'
                                    ? "bg-muted/30 border border-input text-foreground py-2.5 px-4 rounded-2xl rounded-tr-sm shadow-sm leading-relaxed" // User Bubble: Matches input box
                                    : "text-foreground leading-relaxed pl-1" // Bot: minimal/no style
                            )}>
                                <MessageContent content={msg.content} role={msg.role} />
                            </div>
                        </div>
                    </div>
                ))}

                {isThinking && (
                    <div className="flex flex-col w-full mb-4">
                        <div className="flex items-center gap-2 mb-1.5 px-1 opacity-60">
                            <Bot className="w-3 h-3" />
                            <span className="text-[10px] font-bold uppercase tracking-widest">Assistant</span>
                        </div>
                        <div className="pl-1 text-sm text-foreground">
                            {/* Simple pulse for "Thinking..." state before we have content */}
                            <span className="flex items-center gap-2 text-muted-foreground italic text-xs">
                                Thinking <span className="flex gap-1"><span className="animate-bounce">.</span><span className="animate-bounce delay-100">.</span><span className="animate-bounce delay-200">.</span></span>
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area: Redesigned */}
            <div className="p-2 bg-background border-t border-border">
                {/* Image Preview */}
                {pastedImage && (
                    <div className="relative mb-3 inline-block group">
                        <img src={pastedImage} alt="Pasted" className="h-24 rounded-lg border border-border shadow-md" />
                        <button
                            onClick={() => setPastedImage(null)}
                            className="absolute -top-2 -right-2 p-1 bg-destructive text-destructive-foreground rounded-full hover:bg-destructive/90 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    </div>
                )}

                {/* Selected Context Pills */}
                {selectedContexts.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-3">
                        {selectedContexts.map((ctx, i) => (
                            <div key={i} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary text-[10px] font-medium rounded-md max-w-full border border-primary/20">
                                <Quote className="w-3 h-3 shrink-0" />
                                <span className="truncate max-w-[200px]">{ctx.substring(0, 40)}...</span>
                                <button onClick={() => removeSelectedContext(i)} className="hover:text-primary/70 ml-1"><X className="w-3 h-3" /></button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Main Input Box */}
                <div className="w-full bg-muted/30 border border-input rounded-xl focus-within:ring-1 focus-within:ring-ring focus-within:border-primary/50 transition-all shadow-sm">
                    {/* Top Row: User Chat Input */}
                    <textarea
                        ref={textareaRef}
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onPaste={handlePaste}
                        placeholder={selectedContexts.length > 0 ? "Ask about selected text..." : "Ask a question..."}
                        className="w-full bg-transparent text-foreground placeholder:text-muted-foreground border-none rounded-t-xl px-2 py-2 text-sm focus:outline-none resize-none min-h-[50px] max-h-[160px]"
                        style={{
                            height: 'auto',
                            overflow: inputValue.split('\n').length > 5 ? 'auto' : 'hidden'
                        }}
                        rows={1}
                        onInput={(e) => {
                            const target = e.target as HTMLTextAreaElement;
                            target.style.height = 'auto';
                            target.style.height = `${target.scrollHeight}px`;
                        }}
                    />

                    {/* Bottom Row: Controls */}
                    <div className="flex items-center justify-between px-2 py-1 border-t border-border/40 bg-muted/20 rounded-b-xl">
                        {/* Model Selector */}
                        <div className="flex items-center gap-2">
                            <div className="relative group">
                                <select
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModel(e.target.value)}
                                    className="h-7 pl-2 pr-8 text-[10px] font-medium bg-background border border-border rounded-sm focus:outline-none focus:ring-1 focus:ring-primary/50 text-muted-foreground hover:text-foreground hover:border-border/80 transition-all cursor-pointer appearance-none"
                                >
                                    <option value="qwen3-vl:8b">Qwen 3 (Chat)</option>
                                    <option value="gemma3:4b">Gemma (Fast)</option>
                                    <option value="deepseek-coder:6.7b">DeepSeek (Code)</option>
                                </select>
                                <ChevronDown className="w-3 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                            </div>
                        </div>

                        {/* Send Button */}
                        <button
                            onClick={handleSend}
                            disabled={!inputValue.trim() && !pastedImage}
                            className={cn(
                                "p-2 rounded-lg transition-all flex items-center justify-center",
                                inputValue.trim() || pastedImage
                                    ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm scale-100"
                                    : "bg-transparent text-muted-foreground/40 scale-95 cursor-not-allowed"
                            )}
                        >
                            <Send className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
