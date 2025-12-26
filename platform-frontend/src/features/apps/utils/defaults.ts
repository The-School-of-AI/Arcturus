
// Default colors for cards
export const DEFAULT_COLORS = {
    accent: '#eaff00',      // neon-yellow
    background: '#1a1b1e',  // charcoal-900
    text: '#ffffff',        // white
    secondary: '#6b7280',   // gray-500
    border: 'rgba(255,255,255,0.1)', // white/10
    success: '#4ade80',     // green-400
    danger: '#f87171',      // red-400
};

export const COLOR_PRESETS = [
    { name: 'Neon Yellow', value: '#eaff00' },
    { name: 'Cyan', value: '#22d3ee' },
    { name: 'Green', value: '#4ade80' },
    { name: 'Purple', value: '#a855f7' },
    { name: 'Pink', value: '#ec4899' },
    { name: 'Orange', value: '#fb923c' },
    { name: 'Blue', value: '#3b82f6' },
    { name: 'White', value: '#ffffff' },
];

// Default data for each card type
export const getDefaultData = (type: string): any => {
    switch (type) {
        // Basic cards
        case 'metric':
            return { value: '2.4M', change: 12.5, trend: 'up', label: 'Revenue Q3' };
        case 'trend':
            return { value: '$145.2', change: 2.4, label: 'Stock Price' };
        case 'header':
            return { text: 'Dashboard Header' };
        case 'text':
            return { text: 'This is a text block. Edit this content in the inspector panel.' };
        case 'markdown':
            return { content: '# Welcome\n\n- Item 1\n- Item 2\n\n> This is a blockquote.\n\n**Bold** and *italic* text supported.' };
        case 'image':
            return { url: '', alt: 'Image description', caption: 'Image caption' };

        // Finance cards
        case 'profile':
            return {
                name: 'Alphabet Inc.',
                ticker: 'GOOGL',
                description: 'Alphabet Inc. provides online advertising services, cloud computing platform, software, and hardware.',
                sector: 'Technology',
                industry: 'Internet Content & Info',
                employees: '~180,000'
            };
        case 'valuation':
            return { marketPrice: 145.2, fairValue: 180.5, label: 'Undervalued by 19.6%' };
        case 'score_card':
            return { score: 78, subtext: 'Healthy' };
        case 'grade_card':
            return { grade: 'A-', subtext: 'Top Tier' };

        // Chart cards
        case 'line_chart':
            return {
                title: 'Revenue Trend',
                xLabel: 'Month',
                yLabel: 'Revenue ($M)',
                points: [
                    { x: 'Jan', y: 120 },
                    { x: 'Feb', y: 135 },
                    { x: 'Mar', y: 148 },
                    { x: 'Apr', y: 162 },
                    { x: 'May', y: 175 },
                    { x: 'Jun', y: 190 }
                ]
            };
        case 'bar_chart':
            return {
                title: 'Sales by Region',
                xLabel: 'Region',
                yLabel: 'Sales ($K)',
                points: [
                    { x: 'North', y: 450 },
                    { x: 'South', y: 320 },
                    { x: 'East', y: 280 },
                    { x: 'West', y: 510 }
                ]
            };
        case 'area_chart':
            return {
                title: 'User Growth',
                xLabel: 'Quarter',
                yLabel: 'Users (K)',
                points: [
                    { x: 'Q1', y: 1200 },
                    { x: 'Q2', y: 1850 },
                    { x: 'Q3', y: 2400 },
                    { x: 'Q4', y: 3100 }
                ]
            };
        case 'pie_chart':
            return {
                slices: [
                    { label: 'Category A', value: 40, color: '#3b82f6' },
                    { label: 'Category B', value: 30, color: '#10b981' },
                    { label: 'Category C', value: 20, color: '#f59e0b' },
                    { label: 'Category D', value: 10, color: '#ef4444' }
                ]
            };
        case 'candlestick':
            return {
                ticker: 'AAPL',
                ohlc: [
                    { date: '2024-01-01', open: 185, high: 188, low: 183, close: 187 },
                    { date: '2024-01-02', open: 187, high: 190, low: 186, close: 189 },
                    { date: '2024-01-03', open: 189, high: 192, low: 188, close: 191 },
                    { date: '2024-01-04', open: 191, high: 193, low: 189, close: 190 }
                ]
            };

        // Table cards
        case 'table':
            return {
                title: 'Sample Data',
                headers: ['Name', 'Value', 'Status'],
                rows: [
                    ['Revenue', '$2.4M', 'Good'],
                    ['Expenses', '$1.8M', 'Warning'],
                    ['Profit', '$600K', 'Excellent']
                ]
            };
        case 'peer_table':
            return {
                title: 'Peer Comparison',
                peers: [
                    { ticker: 'AAPL', marketCap: '2.5T', pe: 28.5, revenue: '380B' },
                    { ticker: 'MSFT', marketCap: '2.8T', pe: 32.1, revenue: '210B' },
                    { ticker: 'GOOGL', marketCap: '1.8T', pe: 24.3, revenue: '280B' }
                ]
            };
        case 'ratios':
            return {
                ratios: [
                    { name: 'P/E Ratio', value: 24.5, status: 'Fair' },
                    { name: 'PEG Ratio', value: 1.1, status: 'Good' },
                    { name: 'ROE', value: '22%', status: 'Excellent' },
                    { name: 'Debt/Equity', value: 0.45, status: 'Good' }
                ]
            };
        case 'summary':
            return {
                summary: 'Company shows strong fundamentals with healthy revenue growth and solid margins.',
                keyPoints: [
                    'Revenue up 15% YoY',
                    'Market leader in segment',
                    'Strong cash position'
                ]
            };

        // Control cards
        case 'button':
            return { label: 'Run Analysis', action: 'custom', targetUrl: '' };
        case 'input':
            return { placeholder: 'Enter ticker symbol...', defaultValue: '', inputType: 'text' };
        case 'select':
            return {
                placeholder: 'Select option...',
                options: ['Option 1', 'Option 2', 'Option 3'],
                defaultValue: 'Option 1'
            };
        case 'date_picker':
            return { label: 'Date Range', startDate: '2024-01-01', endDate: '2024-12-31' };

        // Dev & Feed cards
        case 'feed':
            return { title: 'News Feed', feedUrl: '', maxItems: 10 };
        case 'log':
            return {
                title: 'System Log',
                logs: [
                    { level: 'info', message: 'System initialized', timestamp: '10:30:00' },
                    { level: 'debug', message: 'Loading data...', timestamp: '10:30:01' },
                    { level: 'success', message: 'Data loaded successfully', timestamp: '10:30:02' }
                ],
                maxLines: 100
            };
        case 'code':
            return {
                title: 'Code Example',
                code: 'def analyze_stock(ticker):\n    """Analyze a stock ticker"""\n    data = fetch_data(ticker)\n    return calculate_metrics(data)',
                language: 'python'
            };
        case 'json':
            return {
                json: {
                    ticker: 'GOOGL',
                    metrics: { revenue: 282.8, net_income: 59.9, cash: 113.7 },
                    flags: ['undervalued', 'high_growth']
                }
            };

        default:
            return {};
    }
};

export const getDefaultStyle = () => ({
    showBorder: true,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    opacity: 100,
    accentColor: DEFAULT_COLORS.accent,
    backgroundColor: 'transparent',
    textColor: '#ffffff',
    successColor: '#4ade80',
    dangerColor: '#f87171',
});
