import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Settings2, Zap, Palette, Database, Info, Trash2, Clock, Terminal, Eye, View, Component, EyeOff, ChevronDown, ChevronRight, X } from 'lucide-react';
import { useAppStore } from '@/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DEFAULT_COLORS, COLOR_PRESETS, getDefaultData, getDefaultStyle, COMPONENT_USAGE } from '../utils/defaults';
import { COMPONENT_CATEGORIES } from './AppsSidebar';

// Import card components for library preview
import { MetricCard } from './cards/MetricCard';
import { TrendMetric } from './cards/TrendMetric';
import { ChartCard } from './cards/ChartCard';
import { PieChartCard } from './cards/PieChartCard';
import { SankeyCard } from './cards/SankeyCard';
import { ScatterCard } from './cards/ScatterCard';
import { HeatmapCard } from './cards/HeatmapCard';
import { TableCard } from './cards/TableCard';
import { ProfileCard } from './cards/ProfileCard';
import { ValuationGauge } from './cards/ValuationGauge';
import { ScoreCard } from './cards/ScoreCard';
import { GradeCard } from './cards/GradeCard';
import { ImageCard } from './cards/ImageCard';
import { MarkdownCard } from './cards/MarkdownCard';
import { DividerCard } from './cards/DividerCard';
import { InputCard, SelectCard, CheckboxCard, SliderCard, ActionButtonCard, RadioGroupCard } from './cards/ControlCards';
import { FeedCard } from './cards/FeedCard';
import { LogStreamCard } from './cards/LogStreamCard';
import { CodeBlockCard } from './cards/CodeBlockCard';
import { JSONViewerCard } from './cards/JSONViewerCard';
import { SummaryGrid } from './cards/SummaryGrid';

// Helper to render a preview component with default data
const renderPreviewComponent = (type: string, data: any, style: any) => {
    const config = {};
    const commonProps = { data, style, config, isInteractive: false };

    switch (type) {
        // Charts & Data
        case 'metric':
            return <MetricCard title="" value={data.value} change={data.change} trend={data.trend} {...commonProps} />;
        case 'trend':
            return <TrendMetric title="" value={data.value} change={data.change} {...commonProps} />;
        case 'line_chart':
            return <ChartCard title="" type="line" {...commonProps} />;
        case 'bar_chart':
            return <ChartCard title="" type="bar" {...commonProps} />;
        case 'area_chart':
            return <ChartCard title="" type="area" {...commonProps} />;
        case 'pie_chart':
            return <PieChartCard title="" {...commonProps} />;
        case 'sankey':
            return <SankeyCard title="" {...commonProps} />;
        case 'scatter':
            return <ScatterCard title="" {...commonProps} />;
        case 'heatmap':
            return <HeatmapCard title="" {...commonProps} />;
        case 'table':
            return <TableCard title="" {...commonProps} />;
        case 'summary':
            return <SummaryGrid title="" {...commonProps} />;

        // Finance
        case 'profile':
            return <ProfileCard {...commonProps} />;
        case 'valuation':
            return <ValuationGauge marketPrice={data.marketPrice} fairValue={data.fairValue} {...commonProps} />;
        case 'score_card':
            return <ScoreCard title="" score={data.score} subtext={data.subtext} {...commonProps} />;
        case 'grade_card':
            return <GradeCard title="" grade={data.grade} subtext={data.subtext} {...commonProps} />;

        // Content
        case 'image':
            return <ImageCard {...commonProps} />;
        case 'markdown':
            return <MarkdownCard content={data.content} {...commonProps} />;
        case 'divider':
            return <DividerCard {...commonProps} />;
        case 'header':
            return <div className="p-4 text-xl font-bold text-foreground">{data.text || 'Dashboard Header'}</div>;
        case 'text':
            return <div className="p-4 text-sm text-muted-foreground">{data.text || 'Text block content...'}</div>;

        // Controls
        case 'button':
            return <ActionButtonCard {...commonProps} />;
        case 'input':
            return <InputCard {...commonProps} />;
        case 'select':
            return <SelectCard {...commonProps} />;
        case 'checkbox':
            return <CheckboxCard {...commonProps} />;
        case 'radio':
            return <RadioGroupCard {...commonProps} />;
        case 'slider':
            return <SliderCard {...commonProps} />;
        case 'date_picker':
            return (
                <div className="p-3 flex flex-col gap-2">
                    <label className="text-[10px] uppercase font-bold text-muted-foreground">Date Range</label>
                    <div className="flex items-center gap-2 p-2 bg-muted border border-border rounded text-[10px] text-foreground">
                        📅 2024-01-01 → Present
                    </div>
                </div>
            );

        // Dev & Feed
        case 'feed':
            return <FeedCard title="" {...commonProps} />;
        case 'log':
            return <LogStreamCard title="" {...commonProps} />;
        case 'code':
            return <CodeBlockCard title="" {...commonProps} />;
        case 'json':
            return <JSONViewerCard title="" {...commonProps} />;

        // Blocks - inline previews (to avoid import complexity)
        case 'stats_trending':
        case 'stats_grid':
        case 'stats_status':
        case 'stats_01':
            return (
                <div className="p-3 grid grid-cols-2 gap-2">
                    {[{ v: '$287K', c: '+8%' }, { v: '$9.4K', c: '-12%' }, { v: '$173K', c: '+2%' }, { v: '$52K', c: '-5%' }].map((s, i) => (
                        <div key={i} className="bg-muted/50 rounded p-2 flex flex-col items-center">
                            <div className="text-sm font-bold text-foreground">{s.v}</div>
                            <div className={`text-[10px] ${s.c.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{s.c}</div>
                        </div>
                    ))}
                </div>
            );
        case 'stats_links':
            return (
                <div className="p-3 flex flex-col gap-2">
                    {['Projects: 12', 'Issues: 47', 'PRs: 8'].map((item, i) => (
                        <div key={i} className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>{item.split(':')[0]}</span>
                            <span className="text-foreground font-bold">{item.split(':')[1]}</span>
                        </div>
                    ))}
                </div>
            );
        case 'simple_table':
            return (
                <div className="p-3 flex flex-col gap-1">
                    <div className="flex gap-2 text-[10px] text-muted-foreground border-b border-border pb-1">
                        <span className="flex-1">Task</span><span className="flex-1">Status</span>
                    </div>
                    {[['Auth', '🟡'], ['UI', '🟢'], ['API', '⚪']].map(([t, s], i) => (
                        <div key={i} className="flex gap-2 text-xs text-muted-foreground">
                            <span className="flex-1">{t}</span><span className="flex-1">{s}</span>
                        </div>
                    ))}
                </div>
            );
        case 'usage_stats':
            return (
                <div className="p-3 flex flex-col gap-2">
                    {[{ n: 'API', p: 35 }, { n: 'Storage', p: 30 }, { n: 'Users', p: 48 }].map((u, i) => (
                        <div key={i} className="flex flex-col gap-1">
                            <div className="flex justify-between text-[10px]">
                                <span className="text-muted-foreground">{u.n}</span>
                                <span className="text-muted-foreground">{u.p}%</span>
                            </div>
                            <div className="h-1.5 bg-charcoal-700 rounded-full overflow-hidden">
                                <div className="h-full bg-neon-yellow rounded-full" style={{ width: `${u.p}%` }} />
                            </div>
                        </div>
                    ))}
                </div>
            );
        case 'storage_card':
            return (
                <div className="p-3 flex flex-col items-center justify-center gap-2">
                    <svg viewBox="0 0 36 36" className="w-16 h-16">
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#374151" strokeWidth="4" />
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#3b82f6" strokeWidth="4" strokeDasharray="30 58" transform="rotate(-90 18 18)" />
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#10b981" strokeWidth="4" strokeDasharray="20 68" strokeDashoffset="-30" transform="rotate(-90 18 18)" />
                    </svg>
                    <div className="text-xs text-muted-foreground">8.3 / 15 GB</div>
                </div>
            );
        case 'accordion_table':
            return (
                <div className="p-3 flex flex-col gap-1">
                    <div className="flex items-center gap-2 text-xs text-foreground bg-muted/50 rounded px-2 py-1">
                        <span className="text-muted-foreground">▶</span>
                        <span>Project A</span>
                        <span className="ml-auto text-neon-yellow">$45K</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground pl-4">
                        <span>└ Frontend</span>
                        <span className="ml-auto">$15K</span>
                    </div>
                </div>
            );

        // Quiz Blocks - Phase 1: Simple Selection
        case 'quiz_mcq':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">What is the capital of France?</div>
                    <div className="flex flex-col gap-2">
                        {['Paris', 'London', 'Berlin', 'Madrid'].map((opt, i) => (
                            <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${i === 0 ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border bg-muted/30'}`}>
                                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${i === 0 ? 'border-neon-yellow' : 'border-muted-foreground'}`}>
                                    {i === 0 && <div className="w-2 h-2 rounded-full bg-neon-yellow" />}
                                </div>
                                <span className={`text-sm ${i === 0 ? 'text-neon-yellow' : 'text-muted-foreground'}`}>{opt}</span>
                            </div>
                        ))}
                    </div>
                    <div className="text-[10px] text-green-400">✓ 10 points</div>
                </div>
            );
        case 'quiz_tf':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">The Earth is flat.</div>
                    <div className="flex gap-3">
                        <div className="flex-1 py-3 px-4 rounded-lg bg-muted/30 border border-border text-center text-sm text-muted-foreground">TRUE</div>
                        <div className="flex-1 py-3 px-4 rounded-lg bg-green-500/20 border border-green-500 text-center text-sm text-green-400 font-medium">FALSE</div>
                    </div>
                </div>
            );
        case 'quiz_multi':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Select all prime numbers:</div>
                    <div className="flex flex-col gap-2">
                        {[['2', true], ['3', true], ['4', false], ['5', true]].map(([opt, checked], i) => (
                            <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${checked ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border bg-muted/30'}`}>
                                <div className={`w-4 h-4 rounded-sm border-2 flex items-center justify-center ${checked ? 'border-neon-yellow bg-neon-yellow' : 'border-muted-foreground'}`}>
                                    {checked && <span className="text-black text-[10px]">✓</span>}
                                </div>
                                <span className={`text-sm ${checked ? 'text-neon-yellow' : 'text-muted-foreground'}`}>{opt}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );
        case 'quiz_rating':
            return (
                <div className="p-4 flex flex-col items-center gap-3">
                    <div className="text-sm font-medium text-foreground">Rate your experience:</div>
                    <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((s) => (
                            <span key={s} className={`text-2xl ${s <= 4 ? 'text-neon-yellow' : 'text-gray-600'}`}>{s <= 4 ? '★' : '☆'}</span>
                        ))}
                    </div>
                    <div className="text-xs text-muted-foreground">4 / 5 stars</div>
                </div>
            );
        case 'quiz_likert':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">I found this course helpful:</div>
                    <div className="flex justify-between items-center gap-2">
                        {['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'].map((label, i) => (
                            <div key={i} className="flex flex-col items-center gap-1">
                                <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${i === 3 ? 'border-neon-yellow bg-neon-yellow' : 'border-gray-500'}`}>
                                    {i === 3 && <div className="w-2 h-2 rounded-full bg-foreground" />}
                                </div>
                                <span className="text-[8px] text-muted-foreground text-center w-12">{label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );
        case 'quiz_nps':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">How likely are you to recommend us?</div>
                    <div className="flex gap-1">
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                            <div key={n} className={`flex-1 py-2 rounded text-xs text-center font-medium ${n <= 6 ? 'bg-red-500/30 text-red-400' : n <= 8 ? 'bg-yellow-500/30 text-yellow-400' : 'bg-green-500/30 text-green-400'
                                } ${n === 9 ? 'ring-2 ring-neon-yellow' : ''}`}>{n}</div>
                        ))}
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                        <span>Not at all likely</span><span>Extremely likely</span>
                    </div>
                </div>
            );
        case 'quiz_ranking':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Rank programming languages:</div>
                    <div className="flex flex-col gap-2">
                        {['1. Python', '2. JavaScript', '3. Go', '4. Rust'].map((item, i) => (
                            <div key={i} className="flex items-center gap-3 bg-muted/30 rounded-lg px-3 py-2 border border-border">
                                <span className="text-muted-foreground">⋮⋮</span>
                                <span className="text-sm text-foreground">{item}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );

        // Phase 2: Input-Based
        case 'quiz_fitb':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm text-foreground">
                        The largest planet in our solar system is <span className="px-2 py-1 bg-neon-yellow/20 text-neon-yellow rounded border border-neon-yellow">Jupiter</span>
                    </div>
                </div>
            );
        case 'quiz_fitmb':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm text-foreground">
                        <span className="px-2 py-1 bg-neon-yellow/20 text-neon-yellow rounded border border-neon-yellow">H₂O</span> is the chemical formula for
                        <span className="px-2 py-1 bg-neon-yellow/20 text-neon-yellow rounded border border-neon-yellow ml-1">water</span>
                    </div>
                </div>
            );
        case 'quiz_number':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">What is 12 × 8?</div>
                    <input type="text" value="96" readOnly className="w-full px-3 py-2 bg-muted border border-neon-yellow rounded text-neon-yellow font-mono text-lg" />
                </div>
            );
        case 'quiz_formula':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Solve: 2x + 5 = 15</div>
                    <div className="px-3 py-2 bg-muted border border-neon-yellow rounded text-neon-yellow font-mono">x = 5</div>
                </div>
            );
        case 'quiz_date':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">When was the Moon landing?</div>
                    <div className="flex items-center gap-2 px-3 py-2 bg-muted border border-border rounded text-muted-foreground">
                        <span>📅</span> <span>July 20, 1969</span>
                    </div>
                </div>
            );
        case 'quiz_essay':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Explain the importance of clean code:</div>
                    <div className="h-32 p-3 bg-muted border border-border rounded text-sm text-muted-foreground">
                        Clean code is important because it improves readability, maintainability, and reduces bugs...
                    </div>
                    <div className="text-[10px] text-muted-foreground">Word count: 12 / 500</div>
                </div>
            );

        // Phase 3: Advanced Interactive
        case 'quiz_match':
            return (
                <div className="p-4 flex gap-4">
                    <div className="flex-1 flex flex-col gap-2">
                        {['HTML', 'CSS', 'JS'].map((l) => <div key={l} className="px-3 py-2 bg-muted/30 rounded border border-border text-sm text-foreground">{l}</div>)}
                    </div>
                    <div className="flex items-center text-neon-yellow">→</div>
                    <div className="flex-1 flex flex-col gap-2">
                        {['Styling', 'Structure', 'Logic'].map((r) => <div key={r} className="px-3 py-2 bg-neon-yellow/10 rounded border border-neon-yellow text-sm text-neon-yellow">{r}</div>)}
                    </div>
                </div>
            );
        case 'quiz_dropdown':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm text-foreground">
                        The <span className="px-2 py-1 bg-muted rounded border border-border">🔽 quick</span> brown
                        <span className="px-2 py-1 bg-muted rounded border border-border ml-1">🔽 fox</span> jumps over the lazy dog.
                    </div>
                </div>
            );
        case 'quiz_code':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Write a function to add two numbers:</div>
                    <div className="bg-charcoal-900 rounded-lg p-3 font-mono text-sm">
                        <div className="text-purple-400">def <span className="text-neon-yellow">add</span>(a, b):</div>
                        <div className="text-foreground pl-4">return a + b</div>
                    </div>
                </div>
            );
        case 'quiz_upload':
            return (
                <div className="p-4 flex flex-col items-center justify-center gap-3">
                    <div className="text-sm font-medium text-foreground">Upload your assignment:</div>
                    <div className="w-full h-24 border-2 border-dashed border-gray-600 rounded-lg flex flex-col items-center justify-center gap-2">
                        <span className="text-2xl">📁</span>
                        <span className="text-xs text-muted-foreground">Drag & drop or click to upload</span>
                    </div>
                </div>
            );
        case 'quiz_image':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Click on the correct part:</div>
                    <div className="relative h-32 bg-gradient-to-br from-gray-700 to-gray-800 rounded-lg flex items-center justify-center">
                        <span className="text-4xl">🖼️</span>
                        <div className="absolute top-4 right-4 w-4 h-4 rounded-full bg-red-500/50 border-2 border-red-500" />
                        <div className="absolute bottom-4 left-4 w-4 h-4 rounded-full bg-neon-yellow/50 border-2 border-neon-yellow" />
                    </div>
                </div>
            );

        // Phase 4: Structural & AI
        case 'quiz_text':
            return (
                <div className="p-4 flex flex-col gap-2">
                    <div className="text-lg font-bold text-foreground">Instructions</div>
                    <div className="text-sm text-muted-foreground">Read each question carefully. You have 30 minutes to complete this quiz.</div>
                </div>
            );
        case 'quiz_section':
            return (
                <div className="p-4 flex items-center justify-center">
                    <div className="text-xl font-bold text-foreground border-b-2 border-neon-yellow pb-1">Section 1: Fundamentals</div>
                </div>
            );
        case 'quiz_media':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="h-32 bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg flex items-center justify-center">
                        <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center">
                            <span className="text-foreground text-xl">▶</span>
                        </div>
                    </div>
                    <div className="text-xs text-muted-foreground text-center">Watch the video before answering</div>
                </div>
            );
        case 'quiz_branch':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">Conditional Logic</div>
                    <div className="text-sm text-muted-foreground">If answer = "Yes" → Go to Question 5</div>
                    <div className="text-sm text-muted-foreground">If answer = "No" → Go to Question 8</div>
                </div>
            );
        case 'quiz_ai':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="text-sm font-medium text-foreground">AI-Graded Task</div>
                    <div className="flex items-center gap-2 text-purple-400">
                        <span className="text-lg">🤖</span>
                        <span className="text-sm">AI will evaluate your response based on the rubric</span>
                    </div>
                </div>
            );

        // New Blocks.so Library Previews
        case 'stats_row':
            return (
                <div className="p-4 grid grid-cols-4 gap-4">
                    {[{ n: 'Profit', v: '$287K', c: '+8.3%' }, { n: 'Late', v: '$9.4K', c: '-12.6%' }, { n: 'Pending', v: '$173K', c: '+2.9%' }, { n: 'Costs', v: '$52K', c: '-5.7%' }].map((s, i) => (
                        <div key={i} className="text-center">
                            <div className="text-[10px] text-muted-foreground">{s.n}</div>
                            <div className="text-sm font-bold text-foreground">{s.v}</div>
                            <div className={`text-[10px] ${s.c.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{s.c}</div>
                        </div>
                    ))}
                </div>
            );
        case 'plan_overview':
            return (
                <div className="p-4 grid grid-cols-2 gap-4">
                    {[{ n: 'Workspaces', p: 20 }, { n: 'Dashboards', p: 10 }, { n: 'Widgets', p: 30 }, { n: 'Storage', p: 50 }].map((s, i) => (
                        <div key={i} className="flex items-center gap-3">
                            <svg viewBox="0 0 36 36" className="w-12 h-12">
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#374151" strokeWidth="4" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#F5C542" strokeWidth="4" strokeDasharray={`${s.p * 0.88} 88`} transform="rotate(-90 18 18)" />
                            </svg>
                            <div>
                                <div className="text-xs font-medium text-foreground">{s.n}</div>
                                <div className="text-[10px] text-muted-foreground">{s.p}% used</div>
                            </div>
                        </div>
                    ))}
                </div>
            );
        case 'trend_cards':
            return (
                <div className="p-4 grid grid-cols-3 gap-4">
                    {[{ n: 'Alpha Corp', v: '$168.59', c: '+10.4%' }, { n: 'Beta Sol', v: '$78.54', c: '+6.3%' }, { n: 'Gamma Inc', v: '$75.68', c: '-7.1%' }].map((s, i) => (
                        <div key={i} className="bg-muted/30 rounded-lg p-3">
                            <div className="text-xs text-foreground">{s.n}</div>
                            <div className={`text-lg font-bold ${s.c.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{s.v}</div>
                            <div className={`text-xs ${s.c.startsWith('+') ? 'text-green-400' : 'text-red-400'}`}>{s.c}</div>
                        </div>
                    ))}
                </div>
            );
        case 'usage_gauge':
            return (
                <div className="p-4 flex flex-col gap-3">
                    {[{ n: 'API Calls', p: 35 }, { n: 'Storage', p: 30 }, { n: 'Users', p: 48 }].map((u, i) => (
                        <div key={i} className="flex flex-col gap-1">
                            <div className="flex justify-between text-xs">
                                <span className="text-muted-foreground">{u.n}</span>
                                <span className="text-muted-foreground">{u.p}%</span>
                            </div>
                            <div className="h-2 bg-charcoal-700 rounded-full overflow-hidden">
                                <div className="h-full bg-neon-yellow rounded-full" style={{ width: `${u.p}%` }} />
                            </div>
                        </div>
                    ))}
                </div>
            );
        case 'storage_donut':
            return (
                <div className="p-4 flex flex-col items-center gap-3">
                    <svg viewBox="0 0 36 36" className="w-20 h-20">
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#374151" strokeWidth="4" />
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#3b82f6" strokeWidth="4" strokeDasharray="30 58" transform="rotate(-90 18 18)" />
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#10b981" strokeWidth="4" strokeDasharray="20 68" strokeDashoffset="-30" transform="rotate(-90 18 18)" />
                        <circle cx="18" cy="18" r="14" fill="none" stroke="#f59e0b" strokeWidth="4" strokeDasharray="15 73" strokeDashoffset="-50" transform="rotate(-90 18 18)" />
                    </svg>
                    <div className="text-sm text-muted-foreground">8.3 / 15 GB</div>
                </div>
            );
        case 'task_table':
        case 'inventory_table':
        case 'project_table':
            return (
                <div className="p-4 text-center text-sm text-muted-foreground">
                    Interactive table component. Add to canvas to configure.
                </div>
            );
        case 'ai_chat':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="self-end bg-neon-yellow/20 rounded-lg px-3 py-2 text-sm text-neon-yellow">Hello, how can I help?</div>
                    <div className="self-start bg-muted rounded-lg px-3 py-2 text-sm text-muted-foreground">AI assistant ready...</div>
                </div>
            );
        case 'share_dialog':
            return (
                <div className="p-4 flex flex-col items-center justify-center gap-2">
                    <div className="text-lg font-medium text-foreground">Share & Collaborate</div>
                    <div className="text-sm text-muted-foreground">Share with your team</div>
                </div>
            );
        case 'file_upload':
            return (
                <div className="p-4 flex flex-col items-center justify-center gap-2">
                    <div className="w-full h-24 border-2 border-dashed border-gray-600 rounded-lg flex items-center justify-center">
                        <span className="text-sm text-muted-foreground">Drag & drop or click to upload</span>
                    </div>
                </div>
            );
        case 'form_layout':
            return (
                <div className="p-4 flex flex-col gap-3">
                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-muted-foreground">Name</label>
                        <div className="h-8 bg-muted border border-border rounded px-2 flex items-center text-sm text-muted-foreground">Enter name...</div>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-muted-foreground">Email</label>
                        <div className="h-8 bg-muted border border-border rounded px-2 flex items-center text-sm text-muted-foreground">Enter email...</div>
                    </div>
                </div>
            );

        default:
            return <div className="flex items-center justify-center h-full text-muted-foreground text-xs">Preview not available</div>;
    }
};

interface AppInspectorProps {
    className?: string;
}

// Helper for Smart Default Dimensions - Uses COMPONENT_CATEGORIES as single source of truth
const getSmartDimensions = (type: string) => {
    for (const category of COMPONENT_CATEGORIES) {
        const item = category.items.find(i => i.type === type);
        if (item && item.defaultW && item.defaultH) {
            return { w: item.defaultW, h: item.defaultH };
        }
    }
    // Fallback default
    return { w: 4, h: 4 };
};

// Define features for each card type
const CARD_FEATURES: Record<string, { name: string; key: string; default: boolean }[]> = {
    metric: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Trend Arrow', key: 'showTrend', default: true },
        { name: 'Show Percentage', key: 'showPercent', default: true },
    ],
    trend: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Sparkline', key: 'showSparkline', default: true },
        { name: 'Show Change', key: 'showChange', default: true },
    ],
    line_chart: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Axis Labels', key: 'showAxis', default: true },
        { name: 'Enable Animation', key: 'animate', default: true },
        { name: 'Curved Lines', key: 'tension', default: true },
        { name: 'Line Thickness', key: 'strokeWidth', default: false }, // Using boolean toggle logic for now or needs number input? Inspector supports boolean mostly. Let's assume number input support or handled elsewhere? 
        // Wait, looking at AppInspector code, it renders switches for everything in CARD_FEATURES. 
        // If I want a number I might need to put it in data or add support. 
        // For now, let's Stick to boolean 'Thick Lines' or just add it and see if I can hack it or if I need to update AppInspector.
        // The Plan said "Stroke Width (Number)". AppInspector currently maps features to Switch (boolean). 
        // I will add 'Thick Lines' as a boolean for now to be safe, or just use a default.
        // Actually, let's look at `AppInspector.tsx` again. 
        // It uses `renderFeatureToggles`. 
        // I'll stick to boolean `Curved Lines` for tension. 
        // For thickness, I can add `Thick Lines`. 
        // Or I can add it to Data Fields? No, it's style.
        // Let's add 'Thick Lines' (key: thickLines) for now.
    ],
    bar_chart: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Values', key: 'showValues', default: false },
    ],
    area_chart: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Axis Labels', key: 'showAxis', default: true },
        { name: 'Enable Animation', key: 'animate', default: true },
        { name: 'Curved Lines', key: 'tension', default: true },
        { name: 'Line Thickness', key: 'strokeWidth', default: false },
    ],
    pie_chart: [
        { name: 'Show Title', key: 'showTitle', default: false },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Percentages', key: 'showPercent', default: true },
        { name: 'Donut Style', key: 'donut', default: true },
    ],
    sankey: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: false },
        { name: 'Show Axis Labels', key: 'showAxisLabels', default: true },
        { name: 'Enable Animation', key: 'animate', default: true },
        { name: 'Auto Multi-Color', key: 'autoMultiColor', default: true },
    ],
    heatmap: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Axis Labels', key: 'showAxisLabels', default: true },
        { name: 'Enable Animation', key: 'animate', default: true },
        { name: 'Auto Multi-Color', key: 'autoMultiColor', default: true },
    ],
    scatter: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
        { name: 'Show Grid', key: 'showGrid', default: true },
        { name: 'Show Axis Labels', key: 'showAxisLabels', default: true },
        { name: 'Enable Animation', key: 'animate', default: true },
        { name: 'Auto Multi-Color', key: 'autoMultiColor', default: true },
    ],
    table: [
        { name: 'Show Header', key: 'showHeader', default: true },
        { name: 'Striped Rows', key: 'striped', default: true },
        { name: 'Hover Highlight', key: 'hoverHighlight', default: true },
        { name: 'Show Borders', key: 'showBorders', default: true },
    ],
    profile: [
        { name: 'Show Logo', key: 'showLogo', default: true },
        { name: 'Show Ticker', key: 'showTicker', default: true },
        { name: 'Show Description', key: 'showDescription', default: true },
        { name: 'Show Sector Info', key: 'showSector', default: true },
    ],
    score_card: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Progress Ring', key: 'showRing', default: true },
    ],
    grade_card: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Use Grade Colors', key: 'useGradeColors', default: true }, // When false, uses accent color instead
    ],
    valuation: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Prices', key: 'showPrices', default: true },
        { name: 'Show Gauge Bar', key: 'showGauge', default: true },
        { name: 'Show Label', key: 'showLabel', default: true },
    ],
    json: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Syntax Highlighting', key: 'highlight', default: true },
        { name: 'Collapsible Nodes', key: 'collapsible', default: true },
        { name: 'Show Line Numbers', key: 'lineNumbers', default: false },
    ],
    code: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Syntax Highlighting', key: 'highlight', default: true },
        { name: 'Show Line Numbers', key: 'lineNumbers', default: true },
        { name: 'Word Wrap', key: 'wordWrap', default: false },
    ],
    markdown: [
        { name: 'Show Title', key: 'showTitle', default: false },
        { name: 'Enable Editing', key: 'editable', default: true },
    ],
    header: [
        { name: 'Bold', key: 'bold', default: true },
        { name: 'Centered', key: 'centered', default: false },
    ],
    text: [
        { name: 'Show Border', key: 'showBorder', default: false },
        { name: 'Editable', key: 'editable', default: true },
    ],
    // blocks.so Components
    stats_trending: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Change %', key: 'showChange', default: true },
    ],
    stats_grid: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    stats_status: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    stats_links: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    simple_table: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Striped Rows', key: 'striped', default: true },
    ],
    // blocks.so Data-Bound Wrappers (4 new)
    stats_01: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    usage_stats: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    storage_card: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    accordion_table: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],
    // New Building Block Features
    checkbox: [{ name: 'Show Label', key: 'showLabel', default: true }],
    switch: [{ name: 'Show Label', key: 'showLabel', default: true }],
    radio_group: [{ name: 'Show Label', key: 'showLabel', default: true }],
    slider: [{ name: 'Show Label', key: 'showLabel', default: true }],
    tags_input: [{ name: 'Show Label', key: 'showLabel', default: true }],
    textarea: [{ name: 'Show Label', key: 'showLabel', default: true }],
    number_input: [{ name: 'Show Label', key: 'showLabel', default: true }],
    color_picker: [{ name: 'Show Label', key: 'showLabel', default: true }],
    rating: [{ name: 'Show Label', key: 'showLabel', default: true }],
    time_picker: [{ name: 'Show Label', key: 'showLabel', default: true }],
    image: [
        { name: 'Fill Area', key: 'fillArea', default: false },
        { name: 'Show Caption', key: 'showCaption', default: true },
    ],
    // Controls - Additional
    button: [
        { name: 'Full Width', key: 'fullWidth', default: false },
        { name: 'Show Icon', key: 'showIcon', default: true },
    ],
    input: [
        { name: 'Show Label', key: 'showLabel', default: true },
        { name: 'Required', key: 'required', default: false },
    ],
    select: [
        { name: 'Show Label', key: 'showLabel', default: true },
        { name: 'Searchable', key: 'searchable', default: false },
        { name: 'Clearable', key: 'clearable', default: true },
    ],
    date_picker: [
        { name: 'Show Label', key: 'showLabel', default: true },
        { name: 'Show Time', key: 'showTime', default: false },
    ],
    // Dev & Feed
    feed: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Auto Refresh', key: 'autoRefresh', default: false },
        { name: 'Show Timestamps', key: 'showTimestamps', default: true },
    ],
    log: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Auto Scroll', key: 'autoScroll', default: true },
        { name: 'Show Timestamps', key: 'showTimestamps', default: true },
    ],
    // Finance Components
    peer_table: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Header', key: 'showHeader', default: true },
        { name: 'Striped Rows', key: 'striped', default: true },
    ],
    ratios: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Categories', key: 'showCategories', default: true },
    ],
    cash_flow: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Totals', key: 'showTotals', default: true },
    ],
    balance_sheet: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Totals', key: 'showTotals', default: true },
    ],
    income_stmt: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Totals', key: 'showTotals', default: true },
    ],
    summary: [
        { name: 'Show Title', key: 'showTitle', default: true },
    ],

    // Quiz Blocks - Shared base features
    quiz_mcq: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Shuffle Options', key: 'shuffleOptions', default: false },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_tf: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_multi: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Shuffle Options', key: 'shuffleOptions', default: false },
        { name: 'Partial Credit', key: 'partialCredit', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_rating: [
        { name: 'Show Feedback', key: 'showFeedback', default: false },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_likert: [
        { name: 'Show Feedback', key: 'showFeedback', default: false },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_nps: [
        { name: 'Show Feedback', key: 'showFeedback', default: false },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_ranking: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Partial Credit', key: 'partialCredit', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_fitb: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Case Sensitive', key: 'caseSensitive', default: false },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_fitmb: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Case Sensitive', key: 'caseSensitive', default: false },
        { name: 'Partial Credit', key: 'partialCredit', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_number: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Allow Tolerance', key: 'allowTolerance', default: false },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_formula: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Allow Tolerance', key: 'allowTolerance', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_date: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_essay: [
        { name: 'Show Word Count', key: 'showWordCount', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_match: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Shuffle Items', key: 'shuffleItems', default: true },
        { name: 'Partial Credit', key: 'partialCredit', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_dropdown: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Partial Credit', key: 'partialCredit', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_code: [
        { name: 'Show Line Numbers', key: 'showLineNumbers', default: true },
        { name: 'Syntax Highlighting', key: 'syntaxHighlight', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_upload: [
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_image: [
        { name: 'Show Feedback', key: 'showFeedback', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    quiz_text: [],
    quiz_section: [],
    quiz_media: [
        { name: 'Auto Play', key: 'autoPlay', default: false },
        { name: 'Show Controls', key: 'showControls', default: true },
    ],
    quiz_branch: [
        { name: 'Show Logic', key: 'showLogic', default: false },
    ],
    quiz_ai: [
        { name: 'Show Rubric', key: 'showRubric', default: true },
        { name: 'Required', key: 'required', default: true },
    ],
    // New Blocks.so Components
    stats_row: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Change %', key: 'showChange', default: true },
    ],
    plan_overview: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Percentage', key: 'showPercent', default: true },
    ],
    trend_cards: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Sparkline', key: 'showSparkline', default: true },
    ],
    usage_gauge: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Labels', key: 'showLabels', default: true },
    ],
    storage_donut: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Legend', key: 'showLegend', default: true },
    ],
    task_table: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Striped Rows', key: 'striped', default: true },
        { name: 'Show Actions', key: 'showActions', default: true },
    ],
    inventory_table: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Filter', key: 'showFilter', default: true },
        { name: 'Striped Rows', key: 'striped', default: true },
    ],
    project_table: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Checkbox', key: 'showCheckbox', default: true },
        { name: 'Show Pagination', key: 'showPagination', default: true },
    ],
    ai_chat: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show History', key: 'showHistory', default: true },
    ],
    share_dialog: [
        { name: 'Show Comments Toggle', key: 'showComments', default: true },
        { name: 'Show Preview', key: 'showPreview', default: true },
    ],
    file_upload: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Progress', key: 'showProgress', default: true },
    ],
    form_layout: [
        { name: 'Show Title', key: 'showTitle', default: true },
        { name: 'Show Labels', key: 'showLabels', default: true },
    ],
};




// Data field definitions for each card type
const CARD_COLORS: Record<string, { name: string; key: string; default: string }[]> = {
    metric: [
        { name: 'Success Color', key: 'successColor', default: '#4ade80' },
        { name: 'Danger Color', key: 'dangerColor', default: '#f87171' },
    ],
    summary: [
        { name: 'Pass Color', key: 'passColor', default: '#4ade80' },
        { name: 'Warn Color', key: 'warnColor', default: '#F5C542' },
        { name: 'Info Color', key: 'infoColor', default: '#3b82f6' },
    ],
    trend: [
        { name: 'Up Color', key: 'successColor', default: '#4ade80' },
        { name: 'Down Color', key: 'dangerColor', default: '#f87171' },
    ],
    score_card: [
        { name: 'Success Color', key: 'successColor', default: '#4ade80' },
        { name: 'Warn Color', key: 'warnColor', default: '#F5C542' },
        { name: 'Danger Color', key: 'dangerColor', default: '#f87171' },
    ],
    grade_card: [
        { name: 'Grade A Color', key: 'gradeA', default: '#22c55e' },
        { name: 'Grade B Color', key: 'gradeB', default: '#4ade80' },
        { name: 'Grade C Color', key: 'gradeC', default: '#eab308' },
        { name: 'Grade D Color', key: 'gradeD', default: '#f97316' },
        { name: 'Grade F Color', key: 'gradeF', default: '#ef4444' },
    ],
    valuation: [
        { name: 'Undervalued Color', key: 'successColor', default: '#4ade80' },
        { name: 'Overvalued Color', key: 'dangerColor', default: '#f87171' },
    ],
    line_chart: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
    bar_chart: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
    area_chart: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
    pie_chart: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
    sankey: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
    scatter: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
    heatmap: [{ name: 'Accent Color', key: 'accentColor', default: '#F5C542' }],
};

const CARD_DATA_FIELDS: Record<string, { name: string; key: string; type: 'text' | 'number' | 'textarea' | 'json' | 'select' | 'image_upload'; options?: string[] }[]> = {
    metric: [
        { name: 'Value', key: 'value', type: 'text' },
        { name: 'Change %', key: 'change', type: 'number' },
        { name: 'Trend', key: 'trend', type: 'select', options: ['up', 'down', 'neutral'] },
    ],
    trend: [
        { name: 'Value', key: 'value', type: 'text' },
        { name: 'Change %', key: 'change', type: 'number' },
        { name: 'Label', key: 'label', type: 'text' },
    ],
    profile: [
        { name: 'Company Name', key: 'name', type: 'text' },
        { name: 'Ticker', key: 'ticker', type: 'text' },
        { name: 'Description', key: 'description', type: 'textarea' },
        { name: 'Sector', key: 'sector', type: 'text' },
        { name: 'Industry', key: 'industry', type: 'text' },
        { name: 'Employees', key: 'employees', type: 'text' },
    ],
    valuation: [
        { name: 'Market Price', key: 'marketPrice', type: 'number' },
        { name: 'Fair Value', key: 'fairValue', type: 'number' },
        { name: 'Label', key: 'label', type: 'text' },
    ],
    score_card: [
        { name: 'Score (0-100)', key: 'score', type: 'number' },
        { name: 'Subtext', key: 'subtext', type: 'text' },
    ],
    grade_card: [
        { name: 'Grade', key: 'grade', type: 'text' },
        { name: 'Subtext', key: 'subtext', type: 'text' },
    ],
    header: [
        { name: 'Text', key: 'text', type: 'text' },
    ],
    text: [
        { name: 'Content', key: 'text', type: 'textarea' },
    ],
    markdown: [
        { name: 'Markdown Content', key: 'content', type: 'textarea' },
    ],
    json: [
        { name: 'JSON Data', key: 'json', type: 'json' },
    ],
    // Chart types
    line_chart: [
        { name: 'Chart Title', key: 'title', type: 'text' },
        { name: 'Series Data (JSON)', key: 'series', type: 'json' },
        { name: 'X Axis Label', key: 'xLabel', type: 'text' },
        { name: 'Y Axis Label', key: 'yLabel', type: 'text' },
    ],
    bar_chart: [
        { name: 'Chart Title', key: 'title', type: 'text' },
        { name: 'Data Points (JSON)', key: 'points', type: 'json' },
        { name: 'X Axis Label', key: 'xLabel', type: 'text' },
        { name: 'Y Axis Label', key: 'yLabel', type: 'text' },
    ],
    area_chart: [
        { name: 'Chart Title', key: 'title', type: 'text' },
        { name: 'Data Points (JSON)', key: 'points', type: 'json' },
        { name: 'X Axis Label', key: 'xLabel', type: 'text' },
        { name: 'Y Axis Label', key: 'yLabel', type: 'text' },
    ],
    pie_chart: [
        { name: 'Slices (JSON Array)', key: 'slices', type: 'json' },
    ],
    sankey: [
        { name: 'Chart Title', key: 'title', type: 'text' },
        { name: 'Nodes (JSON Array)', key: 'nodes', type: 'json' },
        { name: 'Links (JSON Array)', key: 'links', type: 'json' },
    ],
    heatmap: [
        { name: 'Chart Title', key: 'title', type: 'text' },
        { name: 'Data Matrix (JSON)', key: 'matrix', type: 'json' },
        { name: 'X Labels (JSON)', key: 'xLabels', type: 'json' },
        { name: 'Y Labels (JSON)', key: 'yLabels', type: 'json' },
    ],
    scatter: [
        { name: 'Chart Title', key: 'title', type: 'text' },
        { name: 'Points (JSON Array)', key: 'points', type: 'json' },
        { name: 'X Axis Label', key: 'xLabel', type: 'text' },
        { name: 'Y Axis Label', key: 'yLabel', type: 'text' },
    ],
    cash_flow: [
        { name: 'Title', key: 'title', type: 'text' },
        { name: 'Data (JSON)', key: 'data', type: 'json' },
    ],
    balance_sheet: [
        { name: 'Title', key: 'title', type: 'text' },
        { name: 'Data (JSON)', key: 'data', type: 'json' },
    ],
    income_stmt: [
        { name: 'Title', key: 'title', type: 'text' },
        { name: 'Data (JSON)', key: 'data', type: 'json' },
    ],
    // Table types
    table: [
        { name: 'Table Title', key: 'title', type: 'text' },
        { name: 'Headers (JSON Array)', key: 'headers', type: 'json' },
        { name: 'Rows (JSON Array)', key: 'rows', type: 'json' },
    ],
    peer_table: [
        { name: 'Table Title', key: 'title', type: 'text' },
        { name: 'Peers (JSON Array)', key: 'peers', type: 'json' },
    ],
    ratios: [
        { name: 'Ratios (JSON Array)', key: 'ratios', type: 'json' },
    ],
    // Control types
    button: [
        { name: 'Button Label', key: 'label', type: 'text' },
        { name: 'Action Type', key: 'action', type: 'select', options: ['submit', 'reset', 'navigate', 'custom'] },
        { name: 'Target URL', key: 'targetUrl', type: 'text' },
    ],
    input: [
        { name: 'Placeholder', key: 'placeholder', type: 'text' },
        { name: 'Default Value', key: 'defaultValue', type: 'text' },
        { name: 'Input Type', key: 'inputType', type: 'select', options: ['text', 'number', 'email', 'password'] },
    ],
    select: [
        { name: 'Placeholder', key: 'placeholder', type: 'text' },
        { name: 'Options (JSON Array)', key: 'options', type: 'json' },
        { name: 'Default Value', key: 'defaultValue', type: 'text' },
    ],
    date_picker: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Start Date', key: 'startDate', type: 'text' },
        { name: 'End Date', key: 'endDate', type: 'text' },
    ],
    // Dev & Feed types
    feed: [
        { name: 'Feed Title', key: 'title', type: 'text' },
        { name: 'Feed URL', key: 'feedUrl', type: 'text' },
        { name: 'Max Items', key: 'maxItems', type: 'number' },
    ],
    log: [
        { name: 'Log Title', key: 'title', type: 'text' },
        { name: 'Initial Logs (JSON)', key: 'logs', type: 'json' },
        { name: 'Max Lines', key: 'maxLines', type: 'number' },
    ],
    code: [
        { name: 'Code Title', key: 'title', type: 'text' },
        { name: 'Code Content', key: 'code', type: 'textarea' },
        { name: 'Language', key: 'language', type: 'select', options: ['python', 'javascript', 'typescript', 'json', 'sql', 'bash'] },
    ],
    image: [
        { name: 'Image URL', key: 'url', type: 'image_upload' },
        { name: 'Alt Text', key: 'alt', type: 'text' },
        { name: 'Caption', key: 'caption', type: 'text' },
    ],
    summary: [
        { name: 'Executive Summary', key: 'summary', type: 'textarea' },
        { name: 'Key Points (JSON)', key: 'keyPoints', type: 'json' },
    ],
    // blocks.so Components
    stats_trending: [
        { name: 'Stats (JSON Array)', key: 'stats', type: 'json', options: ['[{"name":"Profit","value":"$287K","change":"+8%","changeType":"positive"}]'] },
    ],
    stats_grid: [
        { name: 'Stats (JSON Array)', key: 'stats', type: 'json', options: ['[{"name":"Visitors","value":"10,450","change":"-12%","changeType":"negative"}]'] },
    ],
    stats_status: [
        { name: 'Stats (JSON Array)', key: 'stats', type: 'json', options: ['[{"name":"API Uptime","value":"99.9%","status":"success","statusText":"Operational"}]'] },
    ],
    stats_links: [
        { name: 'Links (JSON Array)', key: 'links', type: 'json', options: ['[{"name":"Projects","value":"12","href":"#"}]'] },
    ],
    simple_table: [
        { name: 'Headers (JSON Array)', key: 'headers', type: 'json', options: ['["Task","Status","Due"]'] },
        { name: 'Rows (JSON Array)', key: 'rows', type: 'json', options: ['[{"cells":["Task 1","Done","2024-03-20"],"status":"success"}]'] },
    ],
    // blocks.so Data-Bound Wrappers
    stats_01: [
        { name: 'Stats (JSON Array)', key: 'stats', type: 'json', options: ['[{"name":"Profit","value":"$287K","change":"+8%","changeType":"positive"}]'] },
    ],
    usage_stats: [
        { name: 'Items (JSON Array)', key: 'items', type: 'json', options: ['[{"name":"API Requests","current":"358K","limit":"1M","percentage":35.8}]'] },
    ],
    storage_card: [
        { name: 'Segments (JSON Array)', key: 'segments', type: 'json', options: ['[{"label":"Documents","value":2400,"color":"bg-blue-500"}]'] },
    ],
    accordion_table: [
        { name: 'Rows (JSON Array)', key: 'rows', type: 'json', options: ['[{"id":"001","name":"Project Alpha","category":"Dev","value":45000,"date":"2024-01-15"}]'] },
    ],
    // New Blocks.so Data-Bound Components
    stats_row: [
        { name: 'Stats (JSON Array)', key: 'stats', type: 'json', options: ['[{"name":"Profit","value":"$287K","change":"+8%","changeType":"positive"}]'] },
    ],
    plan_overview: [
        { name: 'Plan Name', key: 'plan', type: 'text' },
        { name: 'Items (JSON Array)', key: 'items', type: 'json', options: ['[{"name":"Workspaces","current":1,"allowed":5,"percentage":20}]'] },
    ],
    trend_cards: [
        { name: 'Items (JSON Array)', key: 'items', type: 'json', options: ['[{"name":"Alpha Corp","ticker":"ACP","value":"$168.59","change":"+15.86","percentChange":"+10.4%","changeType":"positive"}]'] },
    ],
    usage_gauge: [
        { name: 'Items (JSON Array)', key: 'items', type: 'json', options: ['[{"name":"API Requests","current":358,"limit":1000,"unit":"K"}]'] },
    ],
    storage_donut: [
        { name: 'Used', key: 'used', type: 'number' },
        { name: 'Total', key: 'total', type: 'number' },
        { name: 'Unit', key: 'unit', type: 'text' },
        { name: 'Segments (JSON Array)', key: 'segments', type: 'json', options: ['[{"label":"Documents","value":2.4,"color":"#3b82f6"}]'] },
    ],
    task_table: [
        { name: 'Tasks (JSON Array)', key: 'tasks', type: 'json', options: ['[{"id":"TASK-1","title":"User Auth","assignee":"Sarah K.","status":"completed","priority":"high","dueDate":"2024-03-20"}]'] },
    ],
    inventory_table: [
        { name: 'Products (JSON Array)', key: 'products', type: 'json', options: ['[{"sku":"SKU-8472","name":"Wireless Mouse Pro","stock":245,"category":"Electronics","status":"active","price":"$24.99"}]'] },
    ],
    project_table: [
        { name: 'Projects (JSON Array)', key: 'projects', type: 'json', options: ['[{"id":"1","name":"Project Alpha","date":"Jan 15, 2024","status":"completed","amount":"$2,500"}]'] },
    ],
    ai_chat: [
        { name: 'Placeholder', key: 'placeholder', type: 'text' },
        { name: 'Welcome Message', key: 'welcomeMessage', type: 'text' },
        { name: 'History (JSON Array)', key: 'history', type: 'json', options: ['[{"role":"assistant","content":"Hello! How can I help?"}]'] },
    ],
    share_dialog: [
        { name: 'Title', key: 'title', type: 'text' },
        { name: 'Share URL', key: 'shareUrl', type: 'text' },
        { name: 'Message', key: 'message', type: 'textarea' },
    ],
    file_upload: [
        { name: 'Title', key: 'title', type: 'text' },
        { name: 'Message', key: 'message', type: 'text' },
        { name: 'Max Size (number)', key: 'maxSize', type: 'number' },
        { name: 'Size Unit', key: 'maxSizeUnit', type: 'select', options: ['KB', 'MB', 'GB'] },
        { name: 'Accepted Types (JSON)', key: 'acceptedTypes', type: 'json', options: ['["xlsx","csv","pdf"]'] },
    ],
    form_layout: [
        { name: 'Title', key: 'title', type: 'text' },
        { name: 'Submit Label', key: 'submitLabel', type: 'text' },
        { name: 'Fields (JSON Array)', key: 'fields', type: 'json', options: ['[{"name":"email","label":"Email","type":"email","placeholder":"Enter email","required":true}]'] },
    ],
    // New Building Block Fields
    checkbox: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Start Checked', key: 'checked', type: 'select', options: ['true', 'false'] }
    ],
    switch: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Start On', key: 'checked', type: 'select', options: ['true', 'false'] }
    ],
    radio_group: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Options (comma sep)', key: 'options', type: 'text' },
        { name: 'Default Value', key: 'value', type: 'text' }
    ],
    slider: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Min', key: 'min', type: 'number' },
        { name: 'Max', key: 'max', type: 'number' },
        { name: 'Default Value', key: 'value', type: 'number' }
    ],
    tags_input: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Initial Tags (comma sep)', key: 'value', type: 'text' }
    ],
    textarea: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Placeholder', key: 'placeholder', type: 'text' },
        { name: 'Default Text', key: 'value', type: 'textarea' }
    ],
    number_input: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Min', key: 'min', type: 'number' },
        { name: 'Max', key: 'max', type: 'number' },
        { name: 'Default Value', key: 'value', type: 'number' }
    ],
    color_picker: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Default Color', key: 'value', type: 'text' }
    ],
    rating: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Max Stars', key: 'max', type: 'number' },
        { name: 'Default Rating', key: 'value', type: 'number' }
    ],
    time_picker: [
        { name: 'Label', key: 'label', type: 'text' },
        { name: 'Default Time', key: 'value', type: 'text' }
    ],

    // Quiz Blocks Data Fields
    quiz_mcq: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Options (JSON)', key: 'options', type: 'json' },
        { name: 'Correct Answer (index)', key: 'correctAnswer', type: 'number' },
        { name: 'Points', key: 'score', type: 'number' },
        { name: 'Explanation', key: 'explanation', type: 'textarea' },
    ],
    quiz_tf: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Correct Answer', key: 'correctAnswer', type: 'select', options: ['true', 'false'] },
        { name: 'Points', key: 'score', type: 'number' },
        { name: 'Explanation', key: 'explanation', type: 'textarea' },
    ],
    quiz_multi: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Options (JSON)', key: 'options', type: 'json' },
        { name: 'Correct Answers (JSON indices)', key: 'correctAnswers', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
        { name: 'Explanation', key: 'explanation', type: 'textarea' },
    ],
    quiz_rating: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Max Stars', key: 'maxStars', type: 'number' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_likert: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Items to Rate (JSON)', key: 'items', type: 'json' },
        { name: 'Scale Labels (JSON)', key: 'scaleLabels', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_nps: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_ranking: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Items to Rank (JSON)', key: 'items', type: 'json' },
        { name: 'Correct Order (JSON indices)', key: 'correctOrder', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_fitb: [
        { name: 'Sentence (use ___ for blank)', key: 'sentence', type: 'textarea' },
        { name: 'Correct Answer', key: 'correctAnswer', type: 'text' },
        { name: 'Points', key: 'score', type: 'number' },
        { name: 'Explanation', key: 'explanation', type: 'textarea' },
    ],
    quiz_fitmb: [
        { name: 'Passage (use ___1___, ___2___ etc)', key: 'passage', type: 'textarea' },
        { name: 'Correct Answers (JSON)', key: 'correctAnswers', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_number: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Correct Answer', key: 'correctAnswer', type: 'number' },
        { name: 'Tolerance (+/-)', key: 'tolerance', type: 'number' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_formula: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Formula (LaTeX)', key: 'formula', type: 'text' },
        { name: 'Variables (JSON)', key: 'variables', type: 'json' },
        { name: 'Correct Answer', key: 'correctAnswer', type: 'number' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_date: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Correct Date (YYYY-MM-DD)', key: 'correctAnswer', type: 'text' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_essay: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Min Words', key: 'minWords', type: 'number' },
        { name: 'Max Words', key: 'maxWords', type: 'number' },
        { name: 'Points', key: 'score', type: 'number' },
        { name: 'Rubric', key: 'rubric', type: 'textarea' },
    ],
    quiz_match: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Left Items (JSON)', key: 'leftItems', type: 'json' },
        { name: 'Right Items (JSON)', key: 'rightItems', type: 'json' },
        { name: 'Correct Pairs (JSON)', key: 'correctPairs', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_dropdown: [
        { name: 'Text with Dropdowns (JSON)', key: 'content', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_code: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Starter Code', key: 'starterCode', type: 'textarea' },
        { name: 'Language', key: 'language', type: 'select', options: ['python', 'javascript', 'java', 'cpp', 'sql'] },
        { name: 'Test Cases (JSON)', key: 'testCases', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_upload: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Allowed Types (JSON)', key: 'allowedTypes', type: 'json' },
        { name: 'Max File Size (MB)', key: 'maxSize', type: 'number' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_image: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Image URL', key: 'imageUrl', type: 'image_upload' },
        { name: 'Hotspots (JSON)', key: 'hotspots', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_text: [
        { name: 'Content', key: 'content', type: 'textarea' },
    ],
    quiz_section: [
        { name: 'Section Title', key: 'title', type: 'text' },
        { name: 'Description', key: 'description', type: 'textarea' },
    ],
    quiz_media: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Media URL', key: 'mediaUrl', type: 'text' },
        { name: 'Media Type', key: 'mediaType', type: 'select', options: ['video', 'audio', 'pdf'] },
        { name: 'Points', key: 'score', type: 'number' },
    ],
    quiz_branch: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Branch Logic (JSON)', key: 'branchLogic', type: 'json' },
    ],
    quiz_ai: [
        { name: 'Question', key: 'question', type: 'textarea' },
        { name: 'Rubric (JSON)', key: 'rubric', type: 'json' },
        { name: 'Points', key: 'score', type: 'number' },
    ],
};



export const AppInspector: React.FC<AppInspectorProps> = ({ className }) => {
    const [activeTab, setActiveTab] = useState<'config' | 'triggers' | 'style'>('config');
    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
        appearance: true,
        border: true,
        features: true,
        colors: true,
        data: true,
        properties: true,
    });

    // Connect to Store
    const {
        appCards,
        selectedAppCardId,
        selectedLibraryComponent,
        removeAppCard,
        addAppCard,
        updateAppCardConfig,
        updateAppCardStyle,
        updateAppCardData,
        updateAppCardLabel,
        updateAppCardContext
    } = useAppStore();

    const selectedCard = appCards.find(c => c.id === selectedAppCardId);

    const toggleSection = (section: string) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

    // Handle "Preview Mode" (Library Item Selected)
    if (!selectedCard && selectedLibraryComponent) {
        const onAddClick = () => {
            const newId = `${selectedLibraryComponent.type}-${Date.now()}`;
            const dims = getSmartDimensions(selectedLibraryComponent.type);

            const newCard = {
                id: newId,
                type: selectedLibraryComponent.type,
                label: selectedLibraryComponent.label,
                config: {},
                data: getDefaultData(selectedLibraryComponent.type),
                style: getDefaultStyle()
            };
            addAppCard(newCard, { x: 0, y: Infinity, i: crypto.randomUUID(), ...dims });
        };

        // Get the usage description from centralized data
        const usageText = COMPONENT_USAGE[selectedLibraryComponent.type] || 'A versatile component for your dashboard.';

        // Get default data for the preview
        const previewData = getDefaultData(selectedLibraryComponent.type);
        const previewStyle = getDefaultStyle();

        return (
            <div className={cn("h-full flex flex-col bg-card border-l border-border", className)}>
                <div className="p-4 border-b border-border flex items-center gap-2 bg-primary/5">
                    <div className="p-1.5 rounded bg-primary/20 text-primary">
                        <Component className="w-4 h-4" />
                    </div>
                    <div>
                        <div className="font-bold text-xs uppercase tracking-wider text-primary">Library Preview</div>
                        <div className="text-[10px] text-muted-foreground  opacity-80">{selectedLibraryComponent.type}</div>
                    </div>
                </div>

                <div className="p-4 flex-1 overflow-y-auto space-y-4">
                    {/* Component Name */}
                    <div className="text-left">
                        <h3 className="text-lg font-bold text-foreground">{selectedLibraryComponent.label}</h3>
                    </div>

                    {/* Live Preview - Render the actual component */}
                    <div className="rounded-xl overflow-hidden bg-card border border-border shadow-lg">
                        <div className="w-full aspect-[16/10] relative">
                            <div className="absolute inset-0 p-2">
                                <div className="w-full h-full">
                                    {renderPreviewComponent(selectedLibraryComponent.type, previewData, previewStyle)}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Typical Usage - Below the preview */}
                    <div className="p-3 rounded-lg bg-muted border border-border space-y-1.5">
                        <div className="text-[10px] uppercase font-bold text-primary/80 tracking-wider">Typical Usage</div>
                        <p className="text-xs text-foreground/80 leading-relaxed">{usageText}</p>
                    </div>
                </div>

                <div className="p-4 border-t border-border bg-muted/50">
                    <Button onClick={onAddClick} className="w-full gap-2 bg-primary text-primary-foreground font-bold text-xs h-10 uppercase tracking-widest hover:bg-primary/90">
                        <Zap className="w-4 h-4" /> Add to Canvas
                    </Button>
                </div>
            </div>
        );
    }

    if (!selectedCard) {
        return (
            <div className={cn("h-full flex flex-col items-center justify-center p-8 bg-card text-center space-y-4", className)}>
                <div className="p-4 rounded-full bg-white/5">
                    <Settings2 className="w-8 h-8 text-muted-foreground opacity-20" />
                </div>
                <div className="space-y-1">
                    <h3 className="font-bold text-foreground">No Component Selected</h3>
                    <p className="text-xs text-muted-foreground">Select a card on the builder canvas to configure its logic and appearance.</p>
                </div>
            </div>
        );
    }

    const cardStyle = selectedCard.style || { showBorder: true, opacity: 100, accentColor: DEFAULT_COLORS.accent };
    const cardFeatures = CARD_FEATURES[selectedCard.type] || [];

    return (
        <div className={cn("h-full flex flex-col bg-card border-l border-border", className)}>
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded bg-primary/10 text-primary">
                        <Settings2 className="w-4 h-4" />
                    </div>
                    <div>
                        <div className="font-bold text-xs uppercase tracking-wider">{selectedCard.label}</div>
                        <div className="text-[10px] text-muted-foreground  opacity-50">{selectedCard.id}</div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => useAppStore.getState().clearSelection()}
                        className="p-1.5 hover:bg-red-500/10 text-muted-foreground hover:text-red-400 rounded transition-colors"
                        title="Hide Panel"
                    >
                        <X className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => removeAppCard(selectedCard.id)}
                        className="p-1.5 hover:bg-red-500/10 text-muted-foreground hover:text-red-400 rounded transition-colors"
                        title="Delete Component"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-border bg-muted/50">
                <TabButton active={activeTab === 'config'} onClick={() => setActiveTab('config')} icon={<Settings2 className="w-3.5 h-3.5" />} label="Config" />
                <TabButton active={activeTab === 'triggers'} onClick={() => setActiveTab('triggers')} icon={<Zap className="w-3.5 h-3.5" />} label="Triggers" />
                <TabButton active={activeTab === 'style'} onClick={() => setActiveTab('style')} icon={<Palette className="w-3.5 h-3.5" />} label="Style" />
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-4">
                {activeTab === 'config' && (
                    <div className="space-y-3 animate-in fade-in slide-in-from-right-2 duration-200">

                        {/* PROPERTIES SECTION */}
                        <CollapsibleSection
                            title="Properties"
                            icon={<Terminal className="w-3 h-3" />}
                            expanded={expandedSections.properties}
                            onToggle={() => toggleSection('properties')}
                        >
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Display Title</label>
                                    <Input
                                        value={selectedCard.label}
                                        onChange={(e) => updateAppCardLabel(selectedCard.id, e.target.value)}
                                        className="bg-muted border-border text-xs h-8"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">
                                        Context <span className="text-primary ml-1 opacity-70">(for AI refresh)</span>
                                    </label>
                                    <textarea
                                        value={selectedCard.context || ''}
                                        onChange={(e) => updateAppCardContext(selectedCard.id, e.target.value)}
                                        placeholder="e.g., Bangalore's average commute time in 2026..."
                                        rows={2}
                                        className="w-full bg-muted border border-border rounded text-xs p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none placeholder:text-muted-foreground/50"
                                    />
                                    <div className="text-[9px] text-muted-foreground/60">
                                        Describe what data this component needs. Used by AI to populate values.
                                    </div>
                                </div>
                            </div>
                        </CollapsibleSection>

                        {/* DATA SOURCE SECTION */}
                        <CollapsibleSection
                            title="Data Source"
                            icon={<Database className="w-3 h-3" />}
                            expanded={expandedSections.data}
                            onToggle={() => toggleSection('data')}
                        >
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Source Type</label>
                                    <select
                                        value={selectedCard.config?.dataSource || 'local'}
                                        onChange={(e) => updateAppCardConfig(selectedCard.id, { dataSource: e.target.value })}
                                        className="w-full bg-muted border border-border rounded text-xs px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
                                    >
                                        <option value="local">Local State (Manual)</option>
                                        <option value="agent">Research Agent (Live)</option>
                                        <option value="script">Script Output</option>
                                        <option value="api">External API</option>
                                    </select>
                                </div>

                                {/* Local Data Editor */}
                                {(!selectedCard.config?.dataSource || selectedCard.config?.dataSource === 'local') && (
                                    <div className="space-y-3 pt-2 border-t border-border/50">
                                        <div className="text-[10px] text-primary font-bold uppercase">Edit Card Data</div>

                                        {CARD_DATA_FIELDS[selectedCard.type]?.map(field => (
                                            <div key={field.key} className="space-y-1">
                                                <label className="text-[10px] text-muted-foreground font-medium">{field.name}</label>
                                                {field.type === 'text' && (
                                                    <Input
                                                        value={selectedCard.data?.[field.key] || ''}
                                                        onChange={(e) => updateAppCardData(selectedCard.id, { [field.key]: e.target.value })}
                                                        className="bg-muted border-border text-xs h-8"
                                                    />
                                                )}
                                                {field.type === 'number' && (
                                                    <Input
                                                        type="number"
                                                        value={selectedCard.data?.[field.key] || 0}
                                                        onChange={(e) => updateAppCardData(selectedCard.id, { [field.key]: parseFloat(e.target.value) || 0 })}
                                                        className="bg-muted border-border text-xs h-8"
                                                    />
                                                )}
                                                {field.type === 'textarea' && (
                                                    <textarea
                                                        value={selectedCard.data?.[field.key] || ''}
                                                        onChange={(e) => updateAppCardData(selectedCard.id, { [field.key]: e.target.value })}
                                                        rows={4}
                                                        className="w-full bg-muted border border-border rounded text-xs p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none"
                                                    />
                                                )}
                                                {field.type === 'json' && (
                                                    <div className="space-y-1">
                                                        {field.options && field.options[0] && (
                                                            <div className="text-[9px] text-muted-foreground bg-background rounded px-2 py-1  break-all">
                                                                <span className="text-muted-foreground">Example: </span>{field.options[0]}
                                                            </div>
                                                        )}
                                                        <textarea
                                                            value={typeof selectedCard.data?.[field.key] === 'object'
                                                                ? JSON.stringify(selectedCard.data?.[field.key], null, 2)
                                                                : selectedCard.data?.[field.key] || '{}'}
                                                            onChange={(e) => {
                                                                try {
                                                                    const parsed = JSON.parse(e.target.value);
                                                                    updateAppCardData(selectedCard.id, { [field.key]: parsed });
                                                                } catch {
                                                                    // Keep raw string if invalid JSON
                                                                }
                                                            }}
                                                            rows={6}
                                                            className="w-full bg-muted border border-border rounded text-xs p-2 text-foreground  focus:outline-none focus:ring-1 focus:ring-primary/50 resize-none"
                                                        />
                                                    </div>
                                                )}

                                                {field.type === 'image_upload' && (
                                                    <div className="space-y-2">
                                                        <div className="flex gap-2">
                                                            <Input
                                                                value={selectedCard.data?.[field.key] || ''}
                                                                onChange={(e) => updateAppCardData(selectedCard.id, { [field.key]: e.target.value })}
                                                                className="flex-1 bg-muted border-border text-xs h-8"
                                                                placeholder="Paste internet URL..."
                                                            />
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                className="h-8 px-2 border-border bg-muted hover:bg-white/10 text-[10px]"
                                                                onClick={() => {
                                                                    const input = document.createElement('input');
                                                                    input.type = 'file';
                                                                    input.accept = 'image/*';
                                                                    input.onchange = (e) => {
                                                                        const file = (e.target as HTMLInputElement).files?.[0];
                                                                        if (file) {
                                                                            const reader = new FileReader();
                                                                            reader.onload = (loadEvent) => {
                                                                                const base64 = loadEvent.target?.result as string;
                                                                                updateAppCardData(selectedCard.id, { [field.key]: base64 });
                                                                            };
                                                                            reader.readAsDataURL(file);
                                                                        }
                                                                    };
                                                                    input.click();
                                                                }}
                                                            >
                                                                Upload
                                                            </Button>
                                                        </div>
                                                        {selectedCard.data?.[field.key]?.startsWith('data:image') && (
                                                            <div className="text-[9px] text-neon-yellow/60 italic px-1">
                                                                Local image uploaded (encoded as Base64)
                                                            </div>
                                                        )}
                                                    </div>
                                                )}

                                                {field.type === 'select' && field.options && (
                                                    <select
                                                        value={selectedCard.data?.[field.key] || field.options[0]}
                                                        onChange={(e) => updateAppCardData(selectedCard.id, { [field.key]: e.target.value })}
                                                        className="w-full bg-muted border-border rounded text-xs px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
                                                    >
                                                        {field.options.map(opt => (
                                                            <option key={opt} value={opt}>{opt}</option>
                                                        ))}
                                                    </select>
                                                )}
                                            </div>
                                        ))}

                                        {!CARD_DATA_FIELDS[selectedCard.type] && (
                                            <div className="text-[10px] text-muted-foreground italic py-2">
                                                This card type uses default data. Custom data fields coming soon.
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Agent/Script Info */}
                                {selectedCard.config?.dataSource === 'agent' && (
                                    <div className="p-3 rounded-lg border border-dashed border-primary/30 bg-primary/5 text-center">
                                        <Zap className="w-5 h-5 mx-auto text-primary mb-2" />
                                        <p className="text-[10px] text-muted-foreground">
                                            Data will be populated by the Research Agent in real-time.
                                        </p>
                                    </div>
                                )}

                                {selectedCard.config?.dataSource === 'script' && (
                                    <div className="space-y-2">
                                        <label className="text-[10px] text-muted-foreground font-bold uppercase">Script Path</label>
                                        <Input
                                            value={selectedCard.config?.scriptPath || ''}
                                            onChange={(e) => updateAppCardConfig(selectedCard.id, { scriptPath: e.target.value })}
                                            placeholder="path/to/script.py"
                                            className="bg-muted border-border text-xs h-8 "
                                        />
                                    </div>
                                )}

                                {selectedCard.config?.dataSource === 'api' && (
                                    <div className="space-y-2">
                                        <label className="text-[10px] text-muted-foreground font-bold uppercase">API Endpoint</label>
                                        <Input
                                            value={selectedCard.config?.apiEndpoint || ''}
                                            onChange={(e) => updateAppCardConfig(selectedCard.id, { apiEndpoint: e.target.value })}
                                            placeholder="https://api.example.com/data"
                                            className="bg-muted border-border text-xs h-8 "
                                        />
                                    </div>
                                )}
                            </div>
                        </CollapsibleSection>

                    </div>
                )}

                {activeTab === 'triggers' && (
                    <div className="space-y-5 animate-in fade-in slide-in-from-right-2 duration-200">
                        <SectionHeader icon={<Zap className="w-3 h-3" />} label="Event Triggers" />
                        <div className="p-4 rounded-lg border border-dashed border-border flex flex-col items-center justify-center text-center space-y-2">
                            <Clock className="w-6 h-6 text-muted-foreground opacity-20" />
                            <p className="text-xs text-muted-foreground">Coming soon: Schedule or trigger actions from this card.</p>
                        </div>
                    </div>
                )}

                {activeTab === 'style' && (
                    <div className="space-y-3 animate-in fade-in slide-in-from-right-2 duration-200">

                        {/* BORDER SECTION */}
                        <CollapsibleSection
                            title="Border"
                            icon={<div className="w-3 h-3 border-2 border-current rounded-sm" />}
                            expanded={expandedSections.border}
                            onToggle={() => toggleSection('border')}
                        >
                            <div className="space-y-3">
                                <ToggleRow
                                    label="Show Border"
                                    enabled={cardStyle.showBorder !== false}
                                    onChange={(v) => updateAppCardStyle(selectedCard.id, { showBorder: v })}
                                />

                                {cardStyle.showBorder !== false && (
                                    <>
                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-muted-foreground font-bold uppercase">Border Width</label>
                                            <div className="flex gap-1">
                                                {[1, 2, 3].map(w => (
                                                    <button
                                                        key={w}
                                                        onClick={() => updateAppCardStyle(selectedCard.id, { borderWidth: w })}
                                                        className={cn(
                                                            "flex-1 py-1.5 text-[10px] rounded border transition-colors",
                                                            (cardStyle.borderWidth || 2) === w
                                                                ? "bg-primary/20 border-primary text-primary"
                                                                : "bg-muted border-border text-muted-foreground hover:border-white/20"
                                                        )}
                                                    >
                                                        {w}px
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-muted-foreground font-bold uppercase">Border Color</label>
                                            <ColorPicker
                                                value={cardStyle.borderColor || 'rgba(255,255,255,0.1)'}
                                                onChange={(c) => updateAppCardStyle(selectedCard.id, { borderColor: c })}
                                                presets={[
                                                    { name: 'Default', value: 'rgba(255,255,255,0.1)' },
                                                    { name: 'Light', value: 'rgba(255,255,255,0.2)' },
                                                    { name: 'Accent', value: '#F5C542' },
                                                    { name: 'None', value: 'transparent' },
                                                ]}
                                            />
                                        </div>
                                    </>
                                )}
                            </div>
                        </CollapsibleSection>

                        {/* APPEARANCE SECTION */}
                        <CollapsibleSection
                            title="Appearance"
                            icon={<Palette className="w-3 h-3" />}
                            expanded={expandedSections.appearance}
                            onToggle={() => toggleSection('appearance')}
                        >
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Accent Color</label>
                                    <ColorPicker
                                        value={cardStyle.accentColor || DEFAULT_COLORS.accent}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { accentColor: c })}
                                        presets={COLOR_PRESETS}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Background</label>
                                    <ColorPicker
                                        value={cardStyle.backgroundColor || 'transparent'}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { backgroundColor: c })}
                                        presets={[
                                            { name: 'Default', value: 'hsl(var(--card))' },
                                            { name: 'None', value: 'transparent' },
                                            { name: 'Dark', value: '#0a0b0d' },
                                            { name: 'Charcoal', value: '#1a1b1e' },
                                        ]}
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <div className="flex justify-between items-center">
                                        <label className="text-[10px] text-muted-foreground font-bold uppercase">Opacity</label>
                                        <span className="text-[10px] text-primary ">{cardStyle.opacity || 100}%</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="20"
                                        max="100"
                                        value={cardStyle.opacity || 100}
                                        onChange={(e) => updateAppCardStyle(selectedCard.id, { opacity: parseInt(e.target.value) })}
                                        className="w-full h-1.5 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Corner Radius</label>
                                    <div className="flex gap-1">
                                        {[
                                            { label: 'None', value: 0 },
                                            { label: 'SM', value: 8 },
                                            { label: 'MD', value: 12 },
                                            { label: 'LG', value: 16 },
                                        ].map(opt => (
                                            <button
                                                key={opt.value}
                                                onClick={() => updateAppCardStyle(selectedCard.id, { borderRadius: opt.value })}
                                                className={cn(
                                                    "flex-1 py-1.5 text-[10px] rounded border transition-colors",
                                                    (cardStyle.borderRadius ?? 12) === opt.value
                                                        ? "bg-primary/20 border-primary text-primary"
                                                        : "bg-muted border-border text-muted-foreground hover:border-white/20"
                                                )}
                                            >
                                                {opt.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Auto-Fit Height Toggle */}
                                <ToggleRow
                                    label="Auto-Fit Height"
                                    enabled={selectedCard.config?.autoFit !== false}
                                    onChange={(v) => updateAppCardConfig(selectedCard.id, { autoFit: v })}
                                />
                                <div className="text-[9px] text-muted-foreground/60 -mt-1">
                                    Automatically expand height to fit content. Disable for scrollable cards.
                                </div>
                            </div>
                        </CollapsibleSection>

                        {/* FEATURES SECTION */}
                        {cardFeatures.length > 0 && (
                            <CollapsibleSection
                                title="Features"
                                icon={<Eye className="w-3 h-3" />}
                                expanded={expandedSections.features}
                                onToggle={() => toggleSection('features')}
                            >
                                <div className="space-y-2">
                                    {cardFeatures.map(feature => {
                                        const isEnabled = selectedCard.config?.[feature.key] ?? feature.default;
                                        return (
                                            <ToggleRow
                                                key={feature.key}
                                                label={feature.name}
                                                enabled={isEnabled}
                                                onChange={(v) => updateAppCardConfig(selectedCard.id, { [feature.key]: v })}
                                            />
                                        );
                                    })}
                                </div>
                            </CollapsibleSection>
                        )}

                        {/* COLORS SECTION */}
                        <CollapsibleSection
                            title="Color Overrides"
                            icon={<div className="w-3 h-3 rounded-full bg-gradient-to-br from-primary to-green-400" />}
                            expanded={expandedSections.colors}
                            onToggle={() => toggleSection('colors')}
                        >
                            <div className="space-y-3">
                                <div className="space-y-1.5">
                                    <label className="text-[10px] text-muted-foreground font-bold uppercase">Text Color</label>
                                    <ColorPicker
                                        value={cardStyle.textColor || '#ffffff'}
                                        onChange={(c) => updateAppCardStyle(selectedCard.id, { textColor: c })}
                                        presets={[
                                            { name: 'White', value: '#ffffff' },
                                            { name: 'Gray', value: '#9ca3af' },
                                            { name: 'Accent', value: '#F5C542' },
                                            { name: 'Muted', value: '#6b7280' },
                                        ]}
                                    />
                                </div>

                                {CARD_COLORS[selectedCard.type]?.map(colorOpt => (
                                    <div key={colorOpt.key} className="space-y-1.5">
                                        <label className="text-[10px] text-muted-foreground font-bold uppercase">{colorOpt.name}</label>
                                        <ColorPicker
                                            value={cardStyle[colorOpt.key] || colorOpt.default}
                                            onChange={(c) => updateAppCardStyle(selectedCard.id, { [colorOpt.key]: c })}
                                            presets={COLOR_PRESETS}
                                        />
                                    </div>
                                ))}
                                {!CARD_COLORS[selectedCard.type] && (
                                    <>
                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-muted-foreground font-bold uppercase">Success Color</label>
                                            <ColorPicker
                                                value={cardStyle.successColor || '#4ade80'}
                                                onChange={(c) => updateAppCardStyle(selectedCard.id, { successColor: c })}
                                                presets={[
                                                    { name: 'Green', value: '#4ade80' },
                                                    { name: 'Cyan', value: '#22d3ee' },
                                                    { name: 'Accent', value: '#F5C542' },
                                                ]}
                                            />
                                        </div>

                                        <div className="space-y-1.5">
                                            <label className="text-[10px] text-muted-foreground font-bold uppercase">Danger Color</label>
                                            <ColorPicker
                                                value={cardStyle.dangerColor || '#f87171'}
                                                onChange={(c) => updateAppCardStyle(selectedCard.id, { dangerColor: c })}
                                                presets={[
                                                    { name: 'Red', value: '#f87171' },
                                                    { name: 'Orange', value: '#fb923c' },
                                                    { name: 'Pink', value: '#ec4899' },
                                                ]}
                                            />
                                        </div>
                                    </>
                                )}
                            </div>
                        </CollapsibleSection>

                    </div>
                )}
            </div>
        </div>
    );
};

// Sub-Components

const TabButton = ({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string }) => (
    <button
        onClick={onClick}
        className={cn(
            "flex-1 flex items-center justify-center gap-2 py-3 text-[10px] font-bold uppercase tracking-tighter transition-all relative",
            active ? "text-primary bg-primary/5" : "text-muted-foreground hover:text-foreground"
        )}
    >
        {icon}
        {label}
        {active && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />}
    </button>
);

const SectionHeader = ({ icon, label }: { icon: React.ReactNode, label: string }) => (
    <div className="flex items-center gap-2 pb-2 border-b border-border/50">
        <div className="text-primary">{icon}</div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-foreground">{label}</span>
    </div>
);

const CollapsibleSection = ({
    title,
    icon,
    expanded,
    onToggle,
    children
}: {
    title: string;
    icon: React.ReactNode;
    expanded: boolean;
    onToggle: () => void;
    children: React.ReactNode;
}) => (
    <div className="rounded-lg border border-border/50 overflow-hidden bg-muted/30">
        <button
            onClick={onToggle}
            className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition-colors"
        >
            <div className="flex items-center gap-2">
                <div className="text-primary">{icon}</div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-foreground">{title}</span>
            </div>
            {expanded ? <ChevronDown className="w-3 h-3 text-muted-foreground" /> : <ChevronRight className="w-3 h-3 text-muted-foreground" />}
        </button>
        {expanded && (
            <div className="p-3 pt-0 border-t border-border/50 animate-in slide-in-from-top-1 duration-200">
                {children}
            </div>
        )}
    </div>
);

const ToggleRow = ({ label, enabled, onChange }: { label: string; enabled: boolean; onChange: (v: boolean) => void }) => (
    <div className="flex items-center justify-between py-1">
        <span className="text-xs text-foreground">{label}</span>
        <button
            onClick={() => onChange(!enabled)}
            className={cn(
                "w-9 h-5 rounded-full transition-colors relative",
                enabled ? "bg-primary" : "bg-charcoal-700"
            )}
        >
            <div className={cn(
                "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform",
                enabled ? "translate-x-4" : "translate-x-0.5"
            )} />
        </button>
    </div>
);

const ColorPicker = ({
    value,
    onChange,
    presets
}: {
    value: string;
    onChange: (color: string) => void;
    presets: { name: string; value: string }[];
}) => {
    const [showCustom, setShowCustom] = useState(false);

    return (
        <div className="space-y-2">
            {/* Current Color Preview */}
            <div className="flex items-center gap-2">
                <div
                    className="w-full h-8 rounded border border-border cursor-pointer transition-all hover:border-primary/50"
                    style={{ backgroundColor: value }}
                    onClick={() => setShowCustom(!showCustom)}
                />
            </div>

            {/* Preset Colors */}
            <div className="flex flex-wrap gap-1.5">
                {presets.map(preset => (
                    <button
                        key={preset.value}
                        onClick={() => onChange(preset.value)}
                        className={cn(
                            "w-6 h-6 rounded border-2 transition-all hover:scale-110",
                            value === preset.value ? "border-primary ring-1 ring-primary/50" : "border-transparent"
                        )}
                        style={{ backgroundColor: preset.value }}
                        title={preset.name}
                    />
                ))}
            </div>

            {/* Custom Color Input */}
            {showCustom && (
                <div className="flex gap-2 animate-in slide-in-from-top-1">
                    <input
                        type="color"
                        value={value.startsWith('#') ? value : '#ffffff'}
                        onChange={(e) => onChange(e.target.value)}
                        className="w-8 h-8 rounded cursor-pointer bg-transparent border-0"
                    />
                    <input
                        type="text"
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        placeholder="#ffffff"
                        className="flex-1 bg-muted border border-border rounded text-xs px-2 py-1 text-foreground "
                    />
                </div>
            )}
        </div>
    );
};
