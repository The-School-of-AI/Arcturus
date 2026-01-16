import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import { Search, Brain, Trash2, Plus, AlertCircle, TriangleAlert, Settings2, Monitor, Shield, Code2, Terminal, Heart, Zap, Utensils, Music, Film, BookOpen, Briefcase, Sparkles, RefreshCw, Coffee, Dog, Palette, MessageSquare, Globe, PawPrint, ListTree, GitPullRequest } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

type TabType = 'snippets' | 'preferences';

export const RemmePanel: React.FC = () => {
    const [activeTab, setActiveTab] = useState<TabType>('snippets');

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            {/* Tabs - copied from AppsSidebar */}
            <div className="flex items-center border-b border-border/50 bg-muted/20">
                <button
                    onClick={() => setActiveTab('snippets')}
                    className={cn(
                        "flex-1 py-3 text-[10px] font-bold uppercase tracking-widest transition-all duration-300 relative",
                        activeTab === 'snippets'
                            ? "text-primary bg-primary/5"
                            : "text-muted-foreground/60 hover:text-foreground hover:bg-white/5"
                    )}
                >
                    Snippets
                    {activeTab === 'snippets' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary shadow-[0_0_10px_rgba(var(--primary),0.5)]" />}
                </button>
                <div className="w-px h-4 bg-border/50" />
                <button
                    onClick={() => setActiveTab('preferences')}
                    className={cn(
                        "flex-1 py-3 text-[10px] font-bold uppercase tracking-widest transition-all duration-300 relative",
                        activeTab === 'preferences'
                            ? "text-primary bg-primary/5"
                            : "text-muted-foreground/60 hover:text-foreground hover:bg-white/5"
                    )}
                >
                    Preferences
                    {activeTab === 'preferences' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary shadow-[0_0_10px_rgba(var(--primary),0.5)]" />}
                </button>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto scrollbar-hide">
                {activeTab === 'snippets' ? (
                    <SnippetsView />
                ) : (
                    <PreferencesView />
                )}
            </div>
        </div>
    );
};

// ============================================================================
// SNIPPETS VIEW (Original RemmePanel content)
// ============================================================================

const SnippetsView: React.FC = () => {
    const { memories, fetchMemories, addMemory, deleteMemory, cleanupDanglingMemories, isRemmeAddOpen: isAddOpen, setIsRemmeAddOpen: setIsAddOpen } = useAppStore();
    const [searchQuery, setSearchQuery] = useState("");
    const [expandedMemoryId, setExpandedMemoryId] = useState<string | null>(null);
    const [newMemoryText, setNewMemoryText] = useState("");
    const [isAdding, setIsAdding] = useState(false);

    useEffect(() => {
        fetchMemories();
    }, []);

    const filteredMemories = useMemo(() => {
        let items = [...memories];
        if (searchQuery.trim()) {
            items = items.filter(m =>
                m.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
                m.category.toLowerCase().includes(searchQuery.toLowerCase())
            );
        }
        return items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }, [memories, searchQuery]);

    const danglingCount = useMemo(() => memories.filter(m => m.source_exists === false).length, [memories]);

    const handleAdd = async () => {
        if (!newMemoryText.trim()) return;
        setIsAdding(true);
        try {
            await addMemory(newMemoryText);
            setNewMemoryText("");
            setIsAddOpen(false);
        } finally {
            setIsAdding(false);
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header & Search */}
            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center gap-1.5 shrink-0">
                <div className="relative flex-1 group">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <Input
                        className="w-full bg-background/50 border-transparent focus:bg-background focus:border-border rounded-md text-xs pl-8 pr-2 h-8 transition-all placeholder:text-muted-foreground"
                        placeholder="Search your memories..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80"
                        onClick={() => setIsAddOpen(!isAddOpen)}
                        title="Manual Add"
                    >
                        <Plus className="w-4 h-4" />
                    </Button>

                    <Button
                        variant="ghost"
                        size="icon"
                        disabled={danglingCount === 0}
                        className={cn(
                            "h-8 w-8 shrink-0",
                            danglingCount > 0
                                ? "text-orange-400 hover:text-orange-300 hover:bg-orange-400/10"
                                : "text-muted-foreground opacity-30 cursor-not-allowed"
                        )}
                        onClick={() => {
                            if (confirm(`Cleanup ${danglingCount} memories with missing source sessions?`)) {
                                cleanupDanglingMemories();
                            }
                        }}
                        title={danglingCount > 0 ? `Cleanup ${danglingCount} dangling memories` : "No dangling memories found"}
                    >
                        <TriangleAlert className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Add Memory Form */}
            {isAddOpen && (
                <div className="p-3 border-b border-border/50 bg-primary/5 space-y-2">
                    <Input
                        className="w-full bg-background border-border rounded-md text-xs h-9"
                        placeholder="Enter a memory... (e.g. 'I love horoscopes and astrology')"
                        value={newMemoryText}
                        onChange={(e) => setNewMemoryText(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && newMemoryText.trim()) {
                                handleAdd();
                            }
                        }}
                        autoFocus
                    />
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            onClick={handleAdd}
                            disabled={!newMemoryText.trim() || isAdding}
                            className="h-7 text-xs flex-1"
                        >
                            {isAdding ? 'Adding...' : 'Add Memory'}
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                                setIsAddOpen(false);
                                setNewMemoryText('');
                            }}
                            className="h-7 text-xs"
                        >
                            Cancel
                        </Button>
                    </div>
                </div>
            )}

            {/* List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-hide">
                {filteredMemories.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 px-8 text-center space-y-4 opacity-30">
                        <div className="relative">
                            <Brain className="w-12 h-12 mx-auto" />
                            <Search className="w-6 h-6 absolute -bottom-1 -right-1" />
                        </div>
                        <p className="text-[10px] font-bold uppercase tracking-widest leading-relaxed">No matching memory patterns found</p>
                    </div>
                ) : (
                    filteredMemories.map((memory) => {
                        const isExpanded = expandedMemoryId === memory.id;
                        return (
                            <div
                                key={memory.id}
                                onClick={() => setExpandedMemoryId(isExpanded ? null : memory.id)}
                                className={cn(
                                    "group relative p-4 rounded-xl border transition-all duration-300 cursor-pointer",
                                    "hover:shadow-md",
                                    memory.source_exists === false
                                        ? "border-orange-500/20 hover:border-orange-500/40 bg-orange-500/5"
                                        : "border-border/50 hover:border-primary/50 hover:bg-accent/50"
                                )}
                            >
                                <div className="flex justify-between items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <p className={cn(
                                            "text-[13px] text-foreground/90 leading-relaxed font-normal transition-all duration-300",
                                            isExpanded ? "" : "line-clamp-2"
                                        )}>
                                            {memory.text}
                                        </p>
                                    </div>
                                    <div className="flex flex-col gap-2 -mr-1">
                                        <button
                                            className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-lg text-muted-foreground hover:text-red-400 transition-all duration-200"
                                            onClick={() => deleteMemory(memory.id)}
                                            title="Forget this memory"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>

                                <div className="mt-4 pt-3 border-t border-border/10 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className={cn(
                                            "px-2 py-0.5 rounded-md text-[8px] uppercase font-black tracking-tight",
                                            memory.category === 'derived'
                                                ? "bg-purple-500/10 text-purple-400"
                                                : "bg-blue-500/10 text-blue-400"
                                        )}>
                                            {memory.category}
                                        </div>
                                        <span className="text-[9px] text-muted-foreground/50 font-mono">
                                            {formatDistanceToNow(new Date(memory.created_at))} ago
                                        </span>
                                    </div>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};

// ============================================================================
// PREFERENCES VIEW (Comprehensive UserModel display)
// ============================================================================

interface PreferencesData {
    preferences: any;
    operating_context: any;
    soft_identity: any;
    evidence: any;
    meta: any;
}

const PreferencesView: React.FC = () => {
    const [data, setData] = useState<PreferencesData | null>(null);
    const [loading, setLoading] = useState(true);
    const [bootstrapping, setBootstrapping] = useState(false);
    const [normalizing, setNormalizing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchPreferences = async () => {
        try {
            setLoading(true);
            const response = await axios.get(`${API_BASE}/remme/preferences`);
            if (response.data.status === 'success') {
                setData(response.data);
            } else {
                setError(response.data.error || 'Failed to load preferences');
            }
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPreferences();
    }, []);

    const handleBootstrap = async () => {
        setBootstrapping(true);
        try {
            const response = await axios.post(`${API_BASE}/remme/preferences/bootstrap`);
            if (response.data.status === 'success') {
                await fetchPreferences();
            } else {
                setError(response.data.error || 'Bootstrap failed');
            }
        } catch (err: any) {
            setError(err.message);
        } finally {
            setBootstrapping(false);
        }
    };

    const handleNormalize = async () => {
        setNormalizing(true);
        try {
            await axios.post(`${API_BASE}/remme/normalize`);
            await fetchPreferences();
        } catch (err: any) {
            console.error(err);
        } finally {
            setNormalizing(false);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 px-8 text-center space-y-4 opacity-50">
                <Settings2 className="w-8 h-8 animate-spin" />
                <p className="text-xs">Loading preferences...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center py-20 px-8 text-center space-y-4 text-red-400">
                <AlertCircle className="w-8 h-8" />
                <p className="text-xs">{error}</p>
            </div>
        );
    }

    if (!data) return null;

    const soft = data.soft_identity || {};
    const ctx = data.operating_context || {};
    const prefs = data.preferences || {};
    const meta = data.meta || {};

    return (
        <div className="p-4 space-y-4">
            {/* Bootstrap Button & Confidence */}
            <div className="flex items-center justify-between p-3 rounded-xl border border-border/40 bg-muted/5">
                <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-foreground/70" />
                    <div>
                        <span className="text-xs font-semibold tracking-tight">Profile Awareness</span>
                        <div className="flex items-center gap-3 mt-0.5">
                            <span className="text-[10px] text-muted-foreground/70 font-light">Evidence: <span className="font-semibold text-foreground/80">{meta.total_evidence || 0}</span></span>
                            <span className="text-[10px] text-muted-foreground/70 font-light">Conf: <span className="font-semibold text-foreground/80">{((meta.overall_confidence || 0) * 100).toFixed(0)}%</span></span>
                        </div>
                    </div>
                </div>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={handleBootstrap}
                    disabled={bootstrapping}
                    className="h-8 text-[8px] gap-1.5 border-border hover:border-foreground/40 hover:bg-muted/10 transition-all duration-300"
                >
                    {bootstrapping ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                        <Sparkles className="w-3 h-3" />
                    )}
                    {bootstrapping ? 'PROCESSING' : 'REINDEX'}
                </Button>
            </div>

            {/* Operating Context */}
            <Section title="Operating Context">
                <Row label="OS" value={ctx.os} />
                <Row label="Shell" value={ctx.shell} />
                <Row label="Location" value={ctx.location} />
                <TagRow label="Stack" items={ctx.primary_languages} />
            </Section>

            {/* Discovered Traits (Extras) */}
            {soft.extras && Object.keys(soft.extras).length > 0 && (
                <Section title="Discovered Traits">
                    <div className="grid grid-cols-1 gap-1">
                        {Object.entries(soft.extras).map(([key, item]: [string, any]) => (
                            <div key={key} className="flex items-center justify-between py-1.5 border-b border-border/5 last:border-0 group">
                                <span className="text-[10px] text-muted-foreground uppercase tracking-tight font-medium">
                                    {key.replace(/_/g, " ")}
                                </span>
                                <div className="text-right">
                                    <span className="text-xs text-foreground/80 font-normal block">{String(item.value || 'None')}</span>
                                    {item.confidence && (
                                        <div className="text-[8px] text-muted-foreground/40 font-mono tracking-tighter">
                                            {Math.round(item.confidence * 100)}% CONF
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {/* Output Contract */}
            <Section title="Output Contract">
                <Row label="Verbosity" value={prefs.output_contract?.verbosity} />
                <Row label="Format" value={prefs.output_contract?.format} />
                <TagRow label="Tone" items={prefs.output_contract?.tone_constraints} />
            </Section>

            {/* Tooling */}
            <Section title="Tooling">
                <Row label="Python" value={prefs.tooling?.package_manager?.python || ctx.package_managers?.python?.value} />
                <Row label="JavaScript" value={prefs.tooling?.package_manager?.javascript || ctx.package_managers?.javascript?.value} />
                <TagRow label="Frontend" items={prefs.tooling?.frameworks?.frontend} />
            </Section>

            {/* Preferences Drill-down */}
            {soft.food_and_dining?.dietary_style && (
                <Section title="Food & Dining">
                    <Row label="Diet" value={soft.food_and_dining?.dietary_style} />
                    <TagRow label="Likes" items={soft.food_and_dining?.cuisine_affinities?.likes} />
                </Section>
            )}

            {soft.pets_and_animals?.affinity && (
                <Section title="Animals">
                    <Row label="Affinity" value={soft.pets_and_animals?.affinity} />
                    <TagRow label="Pets" items={soft.pets_and_animals?.ownership?.pet_names} />
                </Section>
            )}

            {/* Interests & Hobbies */}
            {(soft.interests_and_hobbies?.personal_hobbies?.length > 0 || soft.interests_and_hobbies?.professional_interests?.length > 0) && (
                <Section title="Interests">
                    <TagRow label="Professional" items={soft.interests_and_hobbies?.professional_interests} />
                    <TagRow label="Hobbies" items={soft.interests_and_hobbies?.personal_hobbies} />
                </Section>
            )}

            {/* General Preferences */}
            <Section title="General Preferences">
                <Row label="Timezone" value={prefs.general?.timezone} />
                <Row label="Unit System" value={prefs.general?.unit_system} />
                <TagRow label="Languages" items={prefs.general?.preferred_languages} />
            </Section>

            {/* Normalization Button */}
            <div className="flex justify-center pt-4">
                <Button
                    variant="outline"
                    onClick={handleNormalize}
                    disabled={normalizing}
                    className="h-8 text-xs gap-1.5 border-border hover:border-foreground/40 hover:bg-muted/10 transition-all duration-300"
                >
                    {normalizing ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                        <GitPullRequest className="w-3 h-3" />
                    )}
                    {normalizing ? 'Syncing...' : 'Sync with Remme'}
                </Button>
            </div>
        </div>
    );
};

// ============================================================================
// Minimalist Components
// ============================================================================

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
    <div className="space-y-3">
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50 border-l border-foreground/30 pl-2">
            {title}
        </h3>
        <div className="pl-2 space-y-0.5">
            {children}
        </div>
    </div>
);

const Row: React.FC<{ label: string; value: any }> = ({ label, value }) => {
    if (!value) return null;
    const displayValue = Array.isArray(value) ? value.join(", ") : String(value);

    return (
        <div className="grid grid-cols-[100px_1fr] items-baseline py-1 border-b border-border/10 last:border-0 hover:bg-muted/5 transition-colors">
            <span className="text-[11px] text-muted-foreground">{label}</span>
            <span className="text-xs text-foreground/90 font-light">{displayValue}</span>
        </div>
    );
};

const TagRow: React.FC<{ label: string; items: string[] }> = ({ label, items }) => {
    if (!items || items.length === 0) return null;
    return (
        <div className="py-1.5 border-b border-border/10 last:border-0">
            <span className="text-[11px] text-muted-foreground block mb-1.5">{label}</span>
            <div className="flex flex-wrap gap-1.5">
                {items.map((item, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded border border-border/40 text-[10px] text-muted-foreground bg-muted/5">
                        {item}
                    </span>
                ))}
            </div>
        </div>
    );
};
