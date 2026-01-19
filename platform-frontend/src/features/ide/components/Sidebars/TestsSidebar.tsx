import React, { useState, useEffect } from 'react';
import { FlaskConical, Check, AlertTriangle, X, Trash2, ChevronDown, ChevronRight, RefreshCw, Play, CheckSquare, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store';
import { useIdeStore } from '../../store/ideStore';
import { cn } from '@/lib/utils';
import axios from 'axios';
import { API_BASE } from '@/lib/api';

interface TestItem {
    id: string;
    name: string;
    status: 'passing' | 'failing' | 'stale' | 'orphaned' | 'pending';
    type: 'behavior' | 'spec';
    lastRun?: string;
}

interface FileTests {
    file: string;
    tests: TestItem[];
}

type FilterType = 'all' | 'today' | 'verified';

export const TestsSidebar: React.FC = () => {
    const { explorerRootPath, ideActiveDocumentId, ideOpenDocuments } = useAppStore();
    const { selectedTestFile, setSelectedTestFile, activeTests, toggleTest, toggleAllTests } = useIdeStore();

    const [tests, setTests] = useState<TestItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState<FilterType>('all');
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['behavior', 'spec']));

    // Determine the current file to show tests for
    const currentFile = React.useMemo(() => {
        if (ideActiveDocumentId && ideOpenDocuments) {
            const activeDoc = ideOpenDocuments.find(d => d.id === ideActiveDocumentId);
            if (activeDoc?.title) {
                // Use title as the file identifier (it's typically the filename)
                return activeDoc.title;
            }
        }
        return selectedTestFile;
    }, [ideActiveDocumentId, ideOpenDocuments, selectedTestFile]);

    // Fetch tests for current file
    const fetchTests = async () => {
        if (!explorerRootPath || !currentFile) {
            setTests([]);
            return;
        }

        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/tests/for-file`, {
                params: {
                    path: explorerRootPath,
                    file_path: currentFile
                }
            });
            setTests(res.data.tests || []);
        } catch (e) {
            // Tests endpoint may not exist yet, use mock data for now
            setTests([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTests();
    }, [explorerRootPath, currentFile]);

    // Group tests by type
    const groupedTests = React.useMemo(() => {
        const groups: Record<string, TestItem[]> = {
            behavior: [],
            spec: []
        };
        tests.forEach(test => {
            if (groups[test.type]) {
                groups[test.type].push(test);
            }
        });
        return groups;
    }, [tests]);

    // Get active tests for current file
    const currentActiveTests = currentFile ? (activeTests[currentFile] || []) : [];

    const toggleGroup = (group: string) => {
        setExpandedGroups(prev => {
            const next = new Set(prev);
            if (next.has(group)) {
                next.delete(group);
            } else {
                next.add(group);
            }
            return next;
        });
    };

    const handleSelectAll = (enabled: boolean) => {
        if (currentFile) {
            const allTestIds = tests.map(t => t.id);
            toggleAllTests(currentFile, enabled, allTestIds);
        }
    };

    const getStatusIcon = (status: TestItem['status']) => {
        switch (status) {
            case 'passing': return <Check className="w-3 h-3 text-green-400" />;
            case 'failing': return <X className="w-3 h-3 text-red-400" />;
            case 'stale': return <AlertTriangle className="w-3 h-3 text-amber-400" />;
            case 'orphaned': return <Trash2 className="w-3 h-3 text-muted-foreground/50" />;
            default: return <div className="w-3 h-3 rounded-full bg-muted border border-border" />;
        }
    };

    const allSelected = tests.length > 0 && tests.every(t => currentActiveTests.includes(t.id));
    const someSelected = tests.some(t => currentActiveTests.includes(t.id));

    if (!explorerRootPath) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                <FlaskConical className="w-12 h-12 text-muted-foreground" />
                <p className="text-sm">Open a project to manage tests</p>
            </div>
        );
    }

    if (!currentFile) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                <FlaskConical className="w-12 h-12 text-muted-foreground" />
                <p className="text-sm">Select a file in Explorer to see its tests</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-transparent">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-muted/20 border-b border-border/50 shrink-0">
                <div className="flex items-center gap-2">
                    <FlaskConical className="w-3.5 h-3.5 text-primary" />
                    <span className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">
                        Tests
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:bg-white/5"
                        onClick={fetchTests}
                        disabled={loading}
                        title="Refresh tests"
                    >
                        <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
                    </Button>
                </div>
            </div>

            {/* Current File */}
            <div className="px-3 py-2 border-b border-border/10 bg-muted/10">
                <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider mb-1">Testing</p>
                <p className="text-[11px] font-medium truncate" title={currentFile}>
                    {currentFile.split('/').pop()}
                </p>
            </div>

            {/* Filter & Select All */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-border/10">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => handleSelectAll(!allSelected)}
                        className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                        title={allSelected ? "Deselect all" : "Select all"}
                    >
                        {allSelected ? (
                            <CheckSquare className="w-3.5 h-3.5 text-primary" />
                        ) : someSelected ? (
                            <div className="w-3.5 h-3.5 border-2 border-primary/50 rounded-sm bg-primary/20" />
                        ) : (
                            <Square className="w-3.5 h-3.5" />
                        )}
                        <span>All</span>
                    </button>
                </div>

                <select
                    value={filter}
                    onChange={(e) => setFilter(e.target.value as FilterType)}
                    className="text-[10px] bg-muted/30 border border-border/30 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary/20"
                >
                    <option value="all">All Tests</option>
                    <option value="today">Today</option>
                    <option value="verified">Human Verified</option>
                </select>
            </div>

            {/* Tests List */}
            <div className="flex-1 overflow-y-auto scrollbar-thin">
                {tests.length === 0 ? (
                    <div className="flex flex-col items-center justify-center p-8 opacity-30 text-center">
                        <FlaskConical className="w-8 h-8 mb-2" />
                        <p className="text-[10px] tracking-tight uppercase font-bold">No tests found</p>
                        <p className="text-[9px] mt-1 text-muted-foreground">
                            Tests will appear here after generation
                        </p>
                    </div>
                ) : (
                    <div className="py-2">
                        {/* Behavior Tests Group */}
                        {groupedTests.behavior.length > 0 && (
                            <div className="mb-2">
                                <button
                                    onClick={() => toggleGroup('behavior')}
                                    className="w-full px-3 py-1 flex items-center justify-between hover:bg-white/5 transition-colors"
                                >
                                    <div className="flex items-center gap-1">
                                        {expandedGroups.has('behavior') ? (
                                            <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
                                        ) : (
                                            <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
                                        )}
                                        <span className="text-[9px] font-bold text-muted-foreground/70 uppercase tracking-widest">
                                            Behavior
                                        </span>
                                    </div>
                                    <span className="text-[9px] bg-blue-500/20 text-blue-400 px-1 rounded-sm">
                                        {groupedTests.behavior.length}
                                    </span>
                                </button>

                                {expandedGroups.has('behavior') && (
                                    <div className="ml-3">
                                        {groupedTests.behavior.map(test => (
                                            <TestItemRow
                                                key={test.id}
                                                test={test}
                                                isActive={currentActiveTests.includes(test.id)}
                                                onToggle={() => currentFile && toggleTest(currentFile, test.id)}
                                                getStatusIcon={getStatusIcon}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Spec Tests Group */}
                        {groupedTests.spec.length > 0 && (
                            <div className="mb-2">
                                <button
                                    onClick={() => toggleGroup('spec')}
                                    className="w-full px-3 py-1 flex items-center justify-between hover:bg-white/5 transition-colors"
                                >
                                    <div className="flex items-center gap-1">
                                        {expandedGroups.has('spec') ? (
                                            <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
                                        ) : (
                                            <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
                                        )}
                                        <span className="text-[9px] font-bold text-muted-foreground/70 uppercase tracking-widest">
                                            Spec
                                        </span>
                                    </div>
                                    <span className="text-[9px] bg-purple-500/20 text-purple-400 px-1 rounded-sm">
                                        {groupedTests.spec.length}
                                    </span>
                                </button>

                                {expandedGroups.has('spec') && (
                                    <div className="ml-3">
                                        {groupedTests.spec.map(test => (
                                            <TestItemRow
                                                key={test.id}
                                                test={test}
                                                isActive={currentActiveTests.includes(test.id)}
                                                onToggle={() => currentFile && toggleTest(currentFile, test.id)}
                                                getStatusIcon={getStatusIcon}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Footer Actions */}
            <div className="px-3 py-2 border-t border-border/50 bg-muted/5 shrink-0">
                <Button
                    className="w-full h-8 text-[11px] font-bold tracking-wider"
                    disabled={currentActiveTests.length === 0}
                    title="Run selected tests"
                >
                    <Play className="w-3.5 h-3.5 mr-2" />
                    Run {currentActiveTests.length} Test{currentActiveTests.length !== 1 ? 's' : ''}
                </Button>
            </div>
        </div>
    );
};

const TestItemRow: React.FC<{
    test: TestItem;
    isActive: boolean;
    onToggle: () => void;
    getStatusIcon: (status: TestItem['status']) => React.ReactNode;
}> = ({ test, isActive, onToggle, getStatusIcon }) => {
    return (
        <div
            className="group flex items-center gap-2 px-3 py-1.5 hover:bg-white/5 transition-all cursor-pointer select-none"
            onClick={onToggle}
        >
            <button
                className="shrink-0"
                onClick={(e) => { e.stopPropagation(); onToggle(); }}
            >
                {isActive ? (
                    <CheckSquare className="w-3.5 h-3.5 text-primary" />
                ) : (
                    <Square className="w-3.5 h-3.5 text-muted-foreground/50" />
                )}
            </button>

            {getStatusIcon(test.status)}

            <span className={cn(
                "flex-1 text-[10px] truncate",
                test.status === 'orphaned' ? "text-muted-foreground/50 line-through" : "text-foreground/80"
            )}>
                {test.name}
            </span>
        </div>
    );
};
