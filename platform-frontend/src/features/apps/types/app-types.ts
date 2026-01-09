
export type AppCardType =
    // Basics
    | 'header' | 'text' | 'markdown' | 'image' | 'spacer' | 'divider'
    // Charts
    | 'line_chart' | 'bar_chart' | 'area_chart' | 'pie_chart' | 'candlestick' | 'scatter'
    | 'sankey' | 'heatmap'
    // Metrics
    | 'metric' | 'trend' | 'score_card' | 'grade_card'
    // Tables
    | 'table' | 'peer_table' | 'ratios' | 'cash_flow' | 'balance_sheet' | 'income_stmt'
    // Finance / Business
    | 'profile' | 'valuation' | 'summary'
    // Developer
    | 'json' | 'code' | 'log' | 'feed'
    // Controls (Inputs)
    | 'button' | 'input' | 'select' | 'date_picker'
    | 'checkbox' | 'radio_group' | 'switch' | 'tags_input'
    | 'textarea' | 'number_input' | 'color_picker' | 'slider' | 'rating' | 'time_picker'
    // Blocks.so / Dashboards
    | 'stats_trending' | 'stats_grid' | 'stats_status' | 'stats_links'
    | 'simple_table' | 'stats_01' | 'usage_stats' | 'storage_card' | 'accordion_table'
    // Quiz Blocks
    | 'quiz_mcq' | 'quiz_tf' | 'quiz_multi' | 'quiz_rating' | 'quiz_likert' | 'quiz_nps'
    | 'quiz_ranking' | 'quiz_fitb' | 'quiz_fitmb' | 'quiz_number' | 'quiz_formula'
    | 'quiz_date' | 'quiz_essay' | 'quiz_match' | 'quiz_dropdown' | 'quiz_code'
    | 'quiz_upload' | 'quiz_image' | 'quiz_text' | 'quiz_section' | 'quiz_media'
    | 'quiz_branch' | 'quiz_ai'
    // New Blocks.so Components
    | 'stats_row' | 'plan_overview' | 'trend_cards' | 'usage_gauge' | 'storage_donut'
    | 'task_table' | 'inventory_table' | 'project_table'
    | 'ai_chat' | 'share_dialog' | 'file_upload' | 'form_layout';

export interface LibraryComponent {
    type: AppCardType;
    label: string;
    icon: any; // Lucide icon component
    defaultW?: number;
    defaultH?: number;
}

export interface BaseAppCardConfig {
    // Common
    showTitle?: boolean;
    dataSource?: 'local' | 'agent' | 'script' | 'api';
    scriptPath?: string;
    apiEndpoint?: string;
    // Styling overrides specific to config (logical, not just visual)
    centered?: boolean; // For headers
    bold?: boolean; // For headers
}

export interface BaseAppCardStyle {
    showBorder?: boolean;
    borderWidth?: number;
    borderColor?: string;
    borderRadius?: number;
    opacity?: number;
    backgroundColor?: string;
    accentColor?: string;
    textColor?: string;
    successColor?: string;
    dangerColor?: string;
    passColor?: string;
    warnColor?: string;
    infoColor?: string;
    gradeA?: string;
    gradeB?: string;
    gradeC?: string;
    gradeD?: string;
    gradeF?: string;
    [key: string]: any; // Allow dynamic indexing for color overrides
}

// --- Specific Data & Config Types ---

// 1. Metrics
export interface MetricData {
    value?: string | number;
    change?: number;
    trend?: 'up' | 'down' | 'neutral';
}
export interface MetricConfig extends BaseAppCardConfig {
    showTrend?: boolean;
    showPercent?: boolean;
}

export interface TrendData {
    value?: string | number;
    change?: number;
    label?: string;
}
export interface TrendConfig extends BaseAppCardConfig {
    showSparkline?: boolean;
    showChange?: boolean;
}

// 2. Charts
export interface ChartPoint {
    x: string | number;
    y: number;
    category?: string; // For multi-series
}
export interface ChartData {
    points?: ChartPoint[];
    series?: { name: string; data: ChartPoint[] }[]; // Alternative structure
}
export interface ChartConfig extends BaseAppCardConfig {
    showLegend?: boolean;
    showGrid?: boolean;
    showAxis?: boolean;
    animate?: boolean;
    showValues?: boolean;
    xLabel?: string;
    yLabel?: string;
}

export interface PieSlice {
    name: string;
    value: number;
    color?: string;
}
export interface PieChartData {
    slices?: PieSlice[];
}
export interface PieChartConfig extends BaseAppCardConfig {
    showLegend?: boolean;
    showPercent?: boolean;
    donut?: boolean;
}

// 3. Tables
export interface TableData {
    headers?: string[];
    rows?: (string | number | boolean)[][]; // Simple grid
    // OR object array for smarter tables
    records?: Record<string, any>[];
}
export interface TableConfig extends BaseAppCardConfig {
    striped?: boolean;
    hoverHighlight?: boolean;
    showBorders?: boolean;
    showHeader?: boolean;
}

// 4. Content
export interface TextData {
    text?: string;
}
export interface TextConfig extends BaseAppCardConfig {
    editable?: boolean;
    showBorder?: boolean; // Sometimes acts as config
}

export interface MarkdownData {
    content?: string;
}
export interface MarkdownConfig extends BaseAppCardConfig {
    editable?: boolean;
}

export interface ImageData {
    url?: string;
    alt?: string;
    caption?: string;
}

// 5. Controls (Forms)

// Common Options for Select/Radio
export interface OptionItem {
    label: string;
    value: string;
}

export interface ControlData {
    label?: string; // Form label
    placeholder?: string;
    defaultValue?: any;
    value?: any; // Current value usually in local state, but can be pre-filled
    options?: string[] | OptionItem[]; // For select/radio
    min?: number;
    max?: number;
    step?: number;
}
export interface ControlConfig extends BaseAppCardConfig {
    showLabel?: boolean;
    required?: boolean;
    inputType?: 'text' | 'number' | 'email' | 'password'; // For basic input
    action?: 'submit' | 'reset' | 'navigate' | 'custom'; // For buttons
    targetUrl?: string; // For buttons
}

// 6. Developer
export interface CodeData {
    code?: string;
    language?: string;
}
export interface CodeConfig extends BaseAppCardConfig {
    highlight?: boolean;
    lineNumbers?: boolean;
    wordWrap?: boolean;
}

export interface JsonData {
    json?: any;
}
export interface JsonConfig extends BaseAppCardConfig {
    highlight?: boolean;
    collapsible?: boolean;
    lineNumbers?: boolean;
}

// --- Union Type for Data ---
// (We use a loose union or intersection for simplicity in the main AppCard, 
// but can be strict if we use discriminators)
export type AppCardData =
    & MetricData
    & TrendData
    & ChartData
    & PieChartData
    & TableData
    & TextData
    & MarkdownData
    & ImageData
    & ControlData
    & CodeData
    & JsonData
    & Record<string, any>; // Allow extensions

export type AppCardConfig =
    & MetricConfig
    & TrendConfig
    & ChartConfig
    & PieChartConfig
    & TableConfig
    & TextConfig
    & MarkdownConfig
    & ControlConfig
    & CodeConfig
    & JsonConfig
    & Record<string, any>; // Allow extensions

// --- Main Entity ---
export interface AppCard {
    id: string;
    type: AppCardType;
    label: string; // Internal name or default title
    context?: string; // Natural language description of what data this component needs (for AI hydration)
    config: AppCardConfig;
    data?: AppCardData;
    style?: BaseAppCardStyle;
}

export interface SavedApp {
    id: string;
    name: string;
    description?: string; // App description
    lastModified: number;
    lastHydrated?: number; // Timestamp of last data refresh
    cards: AppCard[];
    layout: any[]; // layout-grid layout (can be typed strictly if we import RGL types)
}
