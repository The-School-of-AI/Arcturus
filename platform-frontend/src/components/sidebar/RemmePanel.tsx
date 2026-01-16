import React, { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store';
import { Search, Brain, Trash2, Plus, AlertCircle, TriangleAlert, Settings2, Monitor, Shield, Code2, Terminal, Heart, Zap, Utensils, Music, Film, BookOpen, Briefcase, Sparkles, RefreshCw, Coffee, Dog, Palette, MessageSquare, Globe } from 'lucide-react';
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
                // Refresh data after bootstrap
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
            <div className="flex items-center justify-between p-3 rounded-xl border border-border/50 bg-gradient-to-r from-primary/5 to-transparent">
                <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-primary" />
                    <div>
                        <span className="text-xs font-semibold">Model Confidence</span>
                        <div className="flex items-center gap-3 mt-0.5">
                            <span className="text-[10px] text-muted-foreground">Evidence: <span className="font-bold text-foreground">{meta.preferences_evidence_count || 0}</span></span>
                            <span className="text-[10px] text-muted-foreground">Conf: <span className="font-bold text-primary">{((meta.preferences_confidence || 0) * 100).toFixed(0)}%</span></span>
                        </div>
                    </div>
                </div>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={handleBootstrap}
                    disabled={bootstrapping}
                    className="h-8 text-xs gap-1.5 border-primary/30 hover:border-primary hover:bg-primary/10"
                >
                    {bootstrapping ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                        <Sparkles className="w-3 h-3" />
                    )}
                    {bootstrapping ? 'Extracting...' : 'Bootstrap'}
                </Button>
            </div>

            {/* Operating Context */}
            <PreferenceSection
                icon={<Monitor className="w-4 h-4" />}
                title="Operating Context"
                color="blue"
            >
                <PreferenceGrid items={[
                    { label: 'OS', value: ctx.os },
                    { label: 'Shell', value: ctx.shell },
                    { label: 'CPU', value: ctx.cpu_architecture },
                    { label: 'GPU', value: ctx.has_gpu ? 'Available' : 'Not detected' },
                    { label: 'Location', value: ctx.location },
                ]} />
                {ctx.primary_languages?.length > 0 && (
                    <TagList label="Languages" items={ctx.primary_languages} color="blue" />
                )}
            </PreferenceSection>

            {/* Output Contract */}
            <PreferenceSection
                icon={<Terminal className="w-4 h-4" />}
                title="Output Contract"
                color="green"
            >
                <PreferenceGrid items={[
                    { label: 'Verbosity', value: prefs.output_contract?.verbosity },
                    { label: 'Format', value: prefs.output_contract?.format },
                    { label: 'Clarifications', value: prefs.output_contract?.clarifications },
                ]} />
                {prefs.output_contract?.tone_constraints?.length > 0 && (
                    <TagList label="Tone" items={prefs.output_contract.tone_constraints} color="green" />
                )}
            </PreferenceSection>

            {/* Tooling */}
            <PreferenceSection
                icon={<Code2 className="w-4 h-4" />}
                title="Tooling Defaults"
                color="purple"
            >
                <PreferenceGrid items={[
                    { label: 'Python PM', value: prefs.tooling?.package_manager?.python },
                    { label: 'JS PM', value: prefs.tooling?.package_manager?.javascript },
                ]} />
                {prefs.tooling?.frameworks?.frontend?.length > 0 && (
                    <TagList label="Frontend" items={prefs.tooling.frameworks.frontend} color="purple" />
                )}
                {prefs.tooling?.frameworks?.backend?.length > 0 && (
                    <TagList label="Backend" items={prefs.tooling.frameworks.backend} color="purple" />
                )}
                {prefs.tooling?.testing?.length > 0 && (
                    <TagList label="Testing" items={prefs.tooling.testing} color="purple" />
                )}
            </PreferenceSection>

            {/* Autonomy & Risk */}
            <PreferenceSection
                icon={<Shield className="w-4 h-4" />}
                title="Autonomy & Risk"
                color="orange"
            >
                <PreferenceGrid items={[
                    { label: 'Create Files', value: prefs.autonomy?.create_files },
                    { label: 'Run Shell', value: prefs.autonomy?.run_shell },
                    { label: 'Delete Files', value: prefs.autonomy?.delete_files },
                    { label: 'Git Ops', value: prefs.autonomy?.git_operations },
                    { label: 'Risk', value: prefs.risk_tolerance },
                ]} />
            </PreferenceSection>

            {/* Food & Dining */}
            <PreferenceSection
                icon={<Utensils className="w-4 h-4" />}
                title="Food & Dining"
                color="red"
            >
                <PreferenceGrid items={[
                    { label: 'Dietary Style', value: soft.dietary_style },
                ]} />
                {soft.cuisine_likes?.length > 0 && (
                    <TagList label="Likes" items={soft.cuisine_likes} color="green" />
                )}
                {soft.cuisine_dislikes?.length > 0 && (
                    <TagList label="Dislikes" items={soft.cuisine_dislikes} color="red" />
                )}
                {soft.favorite_foods?.length > 0 && (
                    <TagList label="Favorites" items={soft.favorite_foods} color="yellow" />
                )}
                {soft.food_allergies?.length > 0 && (
                    <TagList label="Allergies" items={soft.food_allergies} color="red" />
                )}
            </PreferenceSection>

            {/* Pets */}
            <PreferenceSection
                icon={<Dog className="w-4 h-4" />}
                title="Pets & Animals"
                color="amber"
            >
                <PreferenceGrid items={[
                    { label: 'Pet Affinity', value: soft.pet_affinity },
                ]} />
                {soft.pet_names?.length > 0 && (
                    <TagList label="Pet Names" items={soft.pet_names} color="amber" />
                )}
            </PreferenceSection>

            {/* Media & Entertainment */}
            <PreferenceSection
                icon={<Film className="w-4 h-4" />}
                title="Media & Entertainment"
                color="pink"
            >
                {soft.music_genres?.length > 0 && (
                    <TagList label="Music" items={soft.music_genres} color="pink" icon={<Music className="w-3 h-3" />} />
                )}
                {soft.movie_genres?.length > 0 && (
                    <TagList label="Movies/TV" items={soft.movie_genres} color="pink" icon={<Film className="w-3 h-3" />} />
                )}
                {soft.book_genres?.length > 0 && (
                    <TagList label="Books" items={soft.book_genres} color="pink" icon={<BookOpen className="w-3 h-3" />} />
                )}
                {soft.podcast_genres?.length > 0 && (
                    <TagList label="Podcasts" items={soft.podcast_genres} color="pink" />
                )}
                {!soft.music_genres?.length && !soft.movie_genres?.length && !soft.book_genres?.length && (
                    <p className="text-[10px] text-muted-foreground/50 italic">No media preferences extracted yet</p>
                )}
            </PreferenceSection>

            {/* Lifestyle */}
            <PreferenceSection
                icon={<Coffee className="w-4 h-4" />}
                title="Lifestyle & Wellness"
                color="teal"
            >
                <PreferenceGrid items={[
                    { label: 'Activity Level', value: soft.activity_level },
                    { label: 'Sleep Rhythm', value: soft.sleep_rhythm },
                    { label: 'Travel Style', value: soft.travel_style },
                ]} />
            </PreferenceSection>

            {/* Communication */}
            <PreferenceSection
                icon={<MessageSquare className="w-4 h-4" />}
                title="Communication Style"
                color="cyan"
            >
                <PreferenceGrid items={[
                    { label: 'Humor', value: soft.humor_tolerance },
                    { label: 'Small Talk', value: soft.small_talk_tolerance },
                    { label: 'Formality', value: soft.formality_preference },
                ]} />
            </PreferenceSection>

            {/* Professional Context */}
            <PreferenceSection
                icon={<Briefcase className="w-4 h-4" />}
                title="Professional Context"
                color="indigo"
            >
                <PreferenceGrid items={[
                    { label: 'Industry', value: soft.industry },
                    { label: 'Role', value: soft.role_type },
                    { label: 'Experience', value: soft.experience_level },
                    { label: 'Company/Org', value: soft.company_or_org },
                ]} />
            </PreferenceSection>

            {/* Interests & Hobbies */}
            <PreferenceSection
                icon={<Heart className="w-4 h-4" />}
                title="Interests & Hobbies"
                color="rose"
            >
                {soft.professional_interests?.length > 0 && (
                    <TagList label="Professional" items={soft.professional_interests} color="indigo" />
                )}
                {soft.personal_hobbies?.length > 0 && (
                    <TagList label="Hobbies" items={soft.personal_hobbies} color="rose" />
                )}
                {soft.learning_interests?.length > 0 && (
                    <TagList label="Learning" items={soft.learning_interests} color="green" />
                )}
                {soft.side_projects?.length > 0 && (
                    <TagList label="Side Projects" items={soft.side_projects} color="blue" />
                )}
                {!soft.professional_interests?.length && !soft.personal_hobbies?.length && (
                    <p className="text-[10px] text-muted-foreground/50 italic">No interests extracted yet</p>
                )}
            </PreferenceSection>

            {/* Anti-Preferences */}
            {(prefs.anti_preferences?.phrases?.length > 0 || prefs.anti_preferences?.moves?.length > 0) && (
                <div className="p-3 rounded-xl border border-red-500/20 bg-red-500/5">
                    <div className="flex items-center gap-2 mb-2">
                        <TriangleAlert className="w-4 h-4 text-red-400" />
                        <span className="text-xs font-semibold text-red-400">Avoid Patterns</span>
                    </div>
                    <div className="space-y-1">
                        {prefs.anti_preferences?.phrases?.map((phrase: string, i: number) => (
                            <div key={i} className="text-[11px] text-red-400/70 font-mono">• "{phrase}"</div>
                        ))}
                        {prefs.anti_preferences?.moves?.map((move: string, i: number) => (
                            <div key={i} className="text-[11px] text-red-400/70">• {move}</div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

// ============================================================================
// Helper Components
// ============================================================================

const colorMap: Record<string, string> = {
    blue: 'text-blue-400 border-blue-500/30 bg-blue-500/5',
    green: 'text-green-400 border-green-500/30 bg-green-500/5',
    purple: 'text-purple-400 border-purple-500/30 bg-purple-500/5',
    orange: 'text-orange-400 border-orange-500/30 bg-orange-500/5',
    red: 'text-red-400 border-red-500/30 bg-red-500/5',
    amber: 'text-amber-400 border-amber-500/30 bg-amber-500/5',
    pink: 'text-pink-400 border-pink-500/30 bg-pink-500/5',
    teal: 'text-teal-400 border-teal-500/30 bg-teal-500/5',
    cyan: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/5',
    indigo: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/5',
    rose: 'text-rose-400 border-rose-500/30 bg-rose-500/5',
    yellow: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/5',
};

const tagColorMap: Record<string, string> = {
    blue: 'bg-blue-500/20 text-blue-400',
    green: 'bg-green-500/20 text-green-400',
    purple: 'bg-purple-500/20 text-purple-400',
    orange: 'bg-orange-500/20 text-orange-400',
    red: 'bg-red-500/20 text-red-400',
    amber: 'bg-amber-500/20 text-amber-400',
    pink: 'bg-pink-500/20 text-pink-400',
    teal: 'bg-teal-500/20 text-teal-400',
    cyan: 'bg-cyan-500/20 text-cyan-400',
    indigo: 'bg-indigo-500/20 text-indigo-400',
    rose: 'bg-rose-500/20 text-rose-400',
    yellow: 'bg-yellow-500/20 text-yellow-400',
};

const PreferenceSection: React.FC<{
    icon: React.ReactNode;
    title: string;
    color: string;
    children: React.ReactNode;
}> = ({ icon, title, color, children }) => (
    <div className={cn("p-3 rounded-xl border transition-all", colorMap[color] || colorMap.blue)}>
        <div className="flex items-center gap-2 mb-3">
            <div className="opacity-80">{icon}</div>
            <span className="text-xs font-semibold">{title}</span>
        </div>
        <div className="space-y-2">
            {children}
        </div>
    </div>
);

const PreferenceGrid: React.FC<{
    items: { label: string; value: any }[];
}> = ({ items }) => (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {items.map((item, i) => (
            <div key={i} className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">{item.label}</span>
                <span className="text-[11px] font-medium text-foreground/80">
                    {item.value || '—'}
                </span>
            </div>
        ))}
    </div>
);

const TagList: React.FC<{
    label: string;
    items: string[];
    color: string;
    icon?: React.ReactNode;
}> = ({ label, items, color, icon }) => (
    <div className="mt-2">
        <div className="flex items-center gap-1 mb-1">
            {icon && <span className="opacity-60">{icon}</span>}
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider">{label}</span>
        </div>
        <div className="flex flex-wrap gap-1">
            {items.map((item, i) => (
                <span
                    key={i}
                    className={cn(
                        "px-1.5 py-0.5 rounded text-[10px] font-medium",
                        tagColorMap[color] || tagColorMap.blue
                    )}
                >
                    {item}
                </span>
            ))}
        </div>
    </div>
);
