import React, { useState, useEffect } from 'react';
import { FlaskConical, Check, AlertTriangle, X, Trash2, ChevronDown, ChevronRight, RefreshCw, Play, CheckSquare, Square, Loader2, Zap, Wrench, Code2 } from 'lucide-react';
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

    code?: string;
    target_line?: number;
    message?: string; // Persisted failure message
}

interface FileTests {
    file: string;
    tests: TestItem[];
}

interface TestFailure {
    test_id: string;
    name: string;
    message: string;
    status: string;
}

type FilterType = 'all' | 'today' | 'verified';

export const TestsSidebar: React.FC = () => {
    const { explorerRootPath, ideActiveDocumentId, ideOpenDocuments, openIdeDocument } = useAppStore();
    const { selectedTestFile, setSelectedTestFile, activeTests, toggleTest, toggleAllTests } = useIdeStore();

    const [tests, setTests] = useState<TestItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generationStatus, setGenerationStatus] = useState<string | null>(null);
    const [lastResults, setLastResults] = useState<{ passed: number; failed: number; total: number } | null>(null);
    const [failedTests, setFailedTests] = useState<TestFailure[]>([]);
    const [feedbackMode, setFeedbackMode] = useState<'always' | 'with_permission' | 'never'>('with_permission');
    const [isFixing, setIsFixing] = useState(false);
    const [filter, setFilter] = useState<FilterType>('all');
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['behavior', 'spec']));
    const [autoRunPending, setAutoRunPending] = useState(false);

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

    // Get active tests for current file
    const currentActiveTests = currentFile ? (activeTests[currentFile] || []) : [];

    // Run selected tests
    const handleRunTests = async () => {
        if (!explorerRootPath || currentActiveTests.length === 0) return;

        setIsRunning(true);
        setLastResults(null);

        try {
            const res = await axios.post(`${API_BASE}/tests/run`, {
                path: explorerRootPath,
                test_ids: currentActiveTests
            });

            if (res.data.success) {
                setLastResults({
                    passed: res.data.passed,
                    failed: res.data.failed,
                    total: res.data.total
                });

                // Store failures for potential fixing
                if (res.data.results) {
                    const failures = res.data.results.filter((r: any) => r.status === 'failing');
                    setFailedTests(failures);
                }

                setFeedbackMode(res.data.feedback_mode || 'with_permission');

                // Update test statuses locally
                if (res.data.results) {
                    setTests(prevTests => prevTests.map(t => {
                        // More robust matching:
                        // 1. Exact ID match
                        // 2. Pytest ID ending with ::test_name (standard)
                        // 3. Result ID contains the test name (fallback)
                        const result = res.data.results.find((r: any) =>
                            r.test_id === t.id ||
                            r.test_id.endsWith("::" + t.id) ||
                            r.test_id.includes(t.name)
                        );

                        if (result) {
                            return {
                                ...t,
                                status: result.status,
                                // If failing, update the failure state implicitly via the failures set,
                                // but here we just ensure the status is visually correct immediately
                            };
                        }
                        return t;
                    }));
                }
            } else {
                // Handle Execution Error (returned by backend)
                setGenerationStatus(`✗ ${res.data.error || "Execution failed"}`);
                setTimeout(() => setGenerationStatus(null), 5000);
            }
        } catch (e) {
            console.error("Failed to run tests:", e);
        } finally {
            setIsRunning(false);
        }
    };

    // Fix failed tests
    const handleFixFailures = async () => {
        if (!explorerRootPath || failedTests.length === 0) return;

        setIsFixing(true);
        try {
            const res = await axios.post(`${API_BASE}/tests/fix`, {
                path: explorerRootPath,
                failures: failedTests
            });

            if (res.data.success) {
                setGenerationStatus(`✓ Fixed ${res.data.fixed_files?.length || 0} files`);
                setFailedTests([]); // Clear failures after fix attempted
                // Re-run tests after fix? Maybe let user do it
                setTimeout(() => setGenerationStatus(null), 3000);
            }
        } catch (e: any) {
            console.error("Fix failed", e);
            setGenerationStatus(`✗ Fix failed: ${e.message}`);
        } finally {
            setIsFixing(false);
        }
    };

    // Listen for arcturus commit events to show auto-generation status
    useEffect(() => {
        const handleArcturusCommit = (event: CustomEvent<{
            test_generation_triggered: boolean;
            python_files_changed: string[];
        }>) => {
            if (event.detail.test_generation_triggered) {
                setIsGenerating(true);
                const files = event.detail.python_files_changed;
                setGenerationStatus(`🧪 Auto-generating tests for ${files.length} file${files.length > 1 ? 's' : ''}...`);

                // Poll for completion (tests endpoint will return updated list)
                const pollInterval = setInterval(async () => {
                    await fetchTests();
                }, 3000);

                // Stop polling after 30s max
                setTimeout(() => {
                    clearInterval(pollInterval);
                    setIsGenerating(false);
                    if (generationStatus?.includes('Auto-generating')) {
                        setGenerationStatus('✓ Test generation complete');
                        setTimeout(() => setGenerationStatus(null), 3000);
                        // Trigger auto-run if tests exist
                        setAutoRunPending(true);
                    }
                }, 30000);
            }
        };

        window.addEventListener('arcturus-commit', handleArcturusCommit as EventListener);
        return () => window.removeEventListener('arcturus-commit', handleArcturusCommit as EventListener);
    }, [explorerRootPath, currentFile]);

    useEffect(() => {
        fetchTests();
    }, [explorerRootPath, currentFile]);

    // Sync missing tests on project load
    useEffect(() => {
        if (!explorerRootPath) return;

        axios.post(`${API_BASE}/tests/sync`, { path: explorerRootPath })
            .then(res => {
                if (res.data.success && res.data.triggered && res.data.triggered.length > 0) {
                    setIsGenerating(true);
                    setGenerationStatus(`Queued generation for ${res.data.triggered.length} pending files`);

                    // Poll for updates
                    const interval = setInterval(fetchTests, 3000);
                    setTimeout(() => {
                        clearInterval(interval);
                        setIsGenerating(false);
                        setGenerationStatus(null);
                        setAutoRunPending(true);
                    }, 30000);
                } else if (res.data.repaired && res.data.repaired.length > 0) {
                    setGenerationStatus(`✓ Repaired manifest for ${res.data.repaired.length} files`);
                    fetchTests();
                }
            })
            .catch(e => console.error("Sync failed", e));
    }, [explorerRootPath]);

    // Auto Run Effect
    useEffect(() => {
        if (autoRunPending && tests.length > 0 && !isRunning && !isGenerating && explorerRootPath) {
            console.log("🚀 Auto-running tests...");
            handleRunTests();
            setAutoRunPending(false);
        }
    }, [autoRunPending, tests, isRunning, isGenerating, explorerRootPath]);

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
            case 'passing': return <Check className="w-3.5 h-3.5 text-green-400" />;
            case 'failing': return <X className="w-3.5 h-3.5 text-red-500" />; // Increased visibility
            case 'stale': return <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />;
            case 'orphaned': return <Trash2 className="w-3.5 h-3.5 text-muted-foreground/50" />;
            default: return <div className="w-3.5 h-3.5 rounded-full bg-muted border border-border" />;
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
                                                failure={failedTests.find(f => f.test_id === test.id || f.test_id.endsWith("::" + test.id) || f.test_id.includes(test.id)) || (test.message ? { test_id: test.id, name: test.name, message: test.message, status: 'failing' } : undefined)}
                                                onOpenTest={() => {
                                                    if (explorerRootPath && currentFile) {
                                                        const testFile1 = `${explorerRootPath}/.arcturus/tests/test_${currentFile}`;
                                                        openIdeDocument({
                                                            id: testFile1,
                                                            title: `test_${currentFile}`,
                                                            file_path: testFile1,
                                                            type: 'code'
                                                        } as any);
                                                    }
                                                }}
                                                onExpand={() => {
                                                    if (explorerRootPath && currentFile) {
                                                        const sutPath = `${explorerRootPath}/${currentFile}`;
                                                        openIdeDocument({
                                                            id: sutPath,
                                                            title: currentFile,
                                                            file_path: sutPath,
                                                            type: 'code',
                                                            initialLine: test.target_line
                                                        } as any);
                                                    }
                                                }}
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
                                                failure={failedTests.find(f => f.test_id === test.id || f.test_id.endsWith("::" + test.id) || f.test_id.includes(test.id)) || (test.message ? { test_id: test.id, name: test.name, message: test.message, status: 'failing' } : undefined)}
                                                onOpenTest={() => {
                                                    if (explorerRootPath && currentFile) {
                                                        const specFile = `${explorerRootPath}/.arcturus/tests/test_${currentFile}`;
                                                        openIdeDocument({
                                                            id: specFile,
                                                            title: `test_${currentFile}`,
                                                            file_path: specFile,
                                                            type: 'code'
                                                        } as any);
                                                    }
                                                }}
                                                onExpand={() => {
                                                    if (explorerRootPath && currentFile) {
                                                        const sutPath = `${explorerRootPath}/${currentFile}`;
                                                        openIdeDocument({
                                                            id: sutPath,
                                                            title: currentFile,
                                                            file_path: sutPath,
                                                            type: 'code'
                                                        } as any);
                                                    }
                                                }}
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
            <div className="px-3 py-2 border-t border-border/50 bg-muted/5 shrink-0 space-y-2">
                {/* Generation Status */}
                {generationStatus && (
                    <div className={cn(
                        "flex items-center gap-2 text-[10px] px-2 py-1.5 rounded",
                        generationStatus.startsWith('✓') ? "bg-green-500/10 text-green-400" :
                            generationStatus.startsWith('✗') ? "bg-red-500/10 text-red-400" :
                                generationStatus.startsWith('⚠') ? "bg-amber-500/10 text-amber-400" :
                                    "bg-blue-500/10 text-blue-400"
                    )}>
                        {isGenerating && <Loader2 className="w-3 h-3 animate-spin" />}
                        <span>{generationStatus}</span>
                    </div>
                )}

                {/* Last Run Results */}
                {lastResults && (
                    <div className="flex items-center justify-between text-[10px] px-2 py-1 bg-muted/30 rounded">
                        <span className="text-muted-foreground">Last Run:</span>
                        <div className="flex items-center gap-2">
                            <span className="text-green-400">{lastResults.passed} passed</span>
                            {lastResults.failed > 0 && (
                                <span className="text-red-400">{lastResults.failed} failed</span>
                            )}
                        </div>
                    </div>
                )}

                {/* Auto-generation indicator (no manual button - tests generate on commit) */}
                {isGenerating && (
                    <div className="flex items-center gap-2 text-[10px] px-2 py-1.5 bg-blue-500/10 text-blue-400 rounded">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        <Zap className="w-3 h-3" />
                        <span>Tests auto-generating on commit...</span>
                    </div>
                )}

                {/* Fix Failures Button */}
                {!isGenerating && failedTests.length > 0 && feedbackMode === 'with_permission' && (
                    <Button
                        variant="outline"
                        className="w-full h-8 text-[11px] font-bold tracking-wider border-dashed border-red-500/30 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        disabled={isFixing}
                        onClick={handleFixFailures}
                        title="Attempt to fix code based on test failures"
                    >
                        {isFixing ? (
                            <>
                                <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                                Fixing...
                            </>
                        ) : (
                            <>
                                <Wrench className="w-3.5 h-3.5 mr-2" />
                                Fix {failedTests.length} Failure{failedTests.length !== 1 ? 's' : ''}
                            </>
                        )}
                    </Button>
                )}

                {/* Run Tests Button */}
                <Button
                    className="w-full h-8 text-[11px] font-bold tracking-wider"
                    disabled={currentActiveTests.length === 0 || isRunning}
                    onClick={handleRunTests}
                    title="Run selected tests"
                >
                    {isRunning ? (
                        <>
                            <RefreshCw className="w-3.5 h-3.5 mr-2 animate-spin" />
                            Running...
                        </>
                    ) : (
                        <>
                            <Play className="w-3.5 h-3.5 mr-2" />
                            Run {currentActiveTests.length} Test{currentActiveTests.length !== 1 ? 's' : ''}
                        </>
                    )}
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
    failure?: TestFailure;
    onOpenTest?: () => void;
    onExpand?: () => void;
}> = ({ test, isActive, onToggle, getStatusIcon, failure, onOpenTest, onExpand }) => {
    const [expanded, setExpanded] = useState(false);
    const prevStatus = React.useRef(test.status);

    // Auto expand only on NEW failure
    useEffect(() => {
        if (test.status === 'failing' && prevStatus.current !== 'failing') {
            setExpanded(true);
        }
        prevStatus.current = test.status;
    }, [test.status]);

    // Initial expand if failing and loaded first time
    useEffect(() => {
        if (test.status === 'failing' && !prevStatus.current) {
            setExpanded(true);
        }
    }, []); // Run once

    const handleRowClick = () => {
        const newExpanded = !expanded;
        setExpanded(newExpanded);
        if (newExpanded && onExpand) {
            onExpand();
        }
    };

    return (
        <div className="flex flex-col border-b border-border/10 last:border-0">
            <div
                className="group flex items-center gap-2 px-3 py-1.5 hover:bg-white/5 transition-all cursor-pointer select-none"
                onClick={handleRowClick}
            >
                <div className="flex items-center gap-2 flex-1 min-w-0">
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

                    <span
                        className={cn(
                            "truncate transition-colors text-[10px]",
                            test.status === 'orphaned' ? "text-muted-foreground/50 line-through" : "text-foreground/80"
                        )}
                        title={test.name}
                    >
                        {test.name}
                    </span>
                </div>

                <div className="flex items-center gap-1">
                    {onOpenTest && (
                        <button
                            onClick={(e) => { e.stopPropagation(); onOpenTest(); }}
                            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded transition-all"
                            title="Open test file"
                        >
                            <FlaskConical className="w-3 h-3 text-muted-foreground" />
                        </button>
                    )}
                    {/* Go to SUT Code Button */}
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            if (onExpand) onExpand();
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded transition-all"
                        title="Go to source code"
                    >
                        <Code2 className="w-3 h-3 text-muted-foreground" />
                    </button>
                    <ChevronRight className={cn("w-3 h-3 text-muted-foreground/50 transition-transform", expanded && "rotate-90")} />
                </div>
            </div>

            {/* Accordion Content */}
            {expanded && (
                <div className="bg-muted/5 pb-2">
                    {/* Failure Message */}
                    {failure && (
                        <div className="mx-3 mt-1 mb-2 p-2 text-[10px] bg-red-500/10 border-l-2 border-red-500/30 rounded-r font-mono whitespace-pre-wrap overflow-x-auto text-red-300">
                            {failure.message}
                        </div>
                    )}

                    {/* Test Code */}
                    {test.code && (
                        <div className="mx-3 mt-1 relative group/code">
                            <div className="text-[10px] font-mono text-muted-foreground bg-muted/30 p-2 rounded overflow-x-auto whitespace-pre border border-border/20">
                                {test.code}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
