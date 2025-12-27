
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
            return {
                url: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe',
                alt: 'Abstract Design',
                caption: 'Default Abstract Header'
            };

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
                title: 'Revenue vs Cost',
                xLabel: 'Month',
                yLabel: 'Amount ($K)',
                series: [
                    {
                        name: 'Revenue',
                        color: '#4ade80',
                        data: [
                            { x: 'Jan', y: 120 },
                            { x: 'Feb', y: 135 },
                            { x: 'Mar', y: 148 },
                            { x: 'Apr', y: 162 },
                            { x: 'May', y: 175 },
                            { x: 'Jun', y: 190 }
                        ]
                    },
                    {
                        name: 'Cost',
                        color: '#f87171',
                        data: [
                            { x: 'Jan', y: 80 },
                            { x: 'Feb', y: 85 },
                            { x: 'Mar', y: 92 },
                            { x: 'Apr', y: 98 },
                            { x: 'May', y: 110 },
                            { x: 'Jun', y: 115 }
                        ]
                    }
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
        case 'sankey':
            return {
                title: 'User Flow',
                nodes: [
                    { name: 'Landing' },
                    { name: 'Sign Up' },
                    { name: 'Explore' },
                    { name: 'Purchase' },
                    { name: 'Drop' }
                ],
                links: [
                    { source: 0, target: 1, value: 50 },
                    { source: 0, target: 2, value: 30 },
                    { source: 0, target: 4, value: 20 },
                    { source: 1, target: 3, value: 40 },
                    { source: 2, target: 3, value: 10 },
                    { source: 2, target: 4, value: 20 }
                ]
            };
        case 'heatmap':
            return {
                title: 'Activity Heatmap',
                xLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
                yLabels: ['Morning', 'Afternoon', 'Evening'],
                matrix: [
                    [10, 20, 30, 40, 50],
                    [20, 40, 60, 80, 100],
                    [5, 15, 25, 35, 45]
                ]
            };
        case 'scatter':
            return {
                title: 'Height vs Weight',
                xLabel: 'Height (cm)',
                yLabel: 'Weight (kg)',
                points: [
                    { x: 170, y: 70 },
                    { x: 180, y: 80 },
                    { x: 165, y: 60 },
                    { x: 190, y: 90 },
                    { x: 175, y: 75 }
                ]
            };
        case 'cash_flow':
        case 'balance_sheet':
        case 'income_stmt':
            return {
                title: 'Financial Statement',
                data: [
                    { label: 'Revenue', value: 1000 },
                    { label: 'Cost of Goods', value: 400 },
                    { label: 'Gross Profit', value: 600 }
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

        // blocks.so Components
        case 'stats_trending':
            return {
                stats: [
                    { name: 'Profit', value: '$287,654', change: '+8.32%', changeType: 'positive' },
                    { name: 'Late payments', value: '$9,435', change: '-12.64%', changeType: 'negative' },
                    { name: 'Pending orders', value: '$173,229', change: '+2.87%', changeType: 'positive' },
                ]
            };
        case 'stats_grid':
            return {
                stats: [
                    { name: 'Unique visitors', value: '10,450', change: '-12.5%', changeType: 'negative' },
                    { name: 'Bounce rate', value: '56.1%', change: '+1.8%', changeType: 'positive' },
                    { name: 'Visit duration', value: '5.2min', change: '+19.7%', changeType: 'positive' },
                    { name: 'Conversion rate', value: '3.2%', change: '-2.4%', changeType: 'negative' },
                ]
            };
        case 'stats_status':
            return {
                stats: [
                    { name: 'API Uptime', value: '99.9%', status: 'success', statusText: 'Operational' },
                    { name: 'Response Time', value: '142ms', status: 'success', statusText: 'Normal' },
                    { name: 'Error Rate', value: '0.4%', status: 'warning', statusText: 'Elevated' },
                    { name: 'Active Users', value: '2,847', status: 'info', statusText: 'Online' },
                ]
            };
        case 'stats_links':
            return {
                links: [
                    { name: 'Active Projects', value: '12', href: '#' },
                    { name: 'Open Issues', value: '47', href: '#' },
                    { name: 'Pull Requests', value: '8', href: '#' },
                    { name: 'Deployments', value: '156', href: '#' },
                ]
            };
        case 'simple_table':
            return {
                headers: ['Task', 'Status', 'Due Date'],
                rows: [
                    { cells: ['User Authentication', 'In Progress', '2024-03-25'], status: 'warning' },
                    { cells: ['Dashboard UI', 'Completed', '2024-03-20'], status: 'success' },
                    { cells: ['API Optimization', 'Pending', '2024-03-22'], status: 'default' },
                ]
            };

        // blocks.so NEW Data-Bound Components
        case 'stats_01':
            return {
                stats: [
                    { name: 'Profit', value: '$287,654', change: '+8.32%', changeType: 'positive' },
                    { name: 'Late payments', value: '$9,435', change: '-12.64%', changeType: 'negative' },
                    { name: 'Pending orders', value: '$173,229', change: '+2.87%', changeType: 'positive' },
                    { name: 'Operating costs', value: '$52,891', change: '-5.73%', changeType: 'negative' },
                ]
            };
        case 'usage_stats':
            return {
                items: [
                    { name: 'API Requests', current: '358K', limit: '1M', percentage: 35.8 },
                    { name: 'Storage', current: '3.07 GB', limit: '10 GB', percentage: 30.7 },
                    { name: 'Bandwidth', current: '4.98 GB', limit: '100 GB', percentage: 5.0 },
                    { name: 'Users', current: '24', limit: '50', percentage: 48 },
                ],
                subtitle: 'Last 30 days'
            };
        case 'storage_card':
            return {
                used: 8300,
                total: 15000,
                unit: 'MB',
                segments: [
                    { label: 'Documents', value: 2400, color: 'bg-blue-500' },
                    { label: 'Photos', value: 1800, color: 'bg-emerald-500' },
                    { label: 'Videos', value: 3200, color: 'bg-amber-500' },
                    { label: 'Music', value: 900, color: 'bg-purple-500' },
                ]
            };
        case 'accordion_table':
            return {
                rows: [
                    {
                        id: '001', name: 'Project Alpha', category: 'Development', value: 45000, date: '2024-01-15',
                        children: [
                            { id: '001-01', name: 'Frontend Module', category: 'Development', value: 15000, date: '2024-01-16' },
                            { id: '001-02', name: 'Backend Module', category: 'Development', value: 20000, date: '2024-01-21' },
                        ]
                    },
                    {
                        id: '002', name: 'Marketing Campaign', category: 'Marketing', value: 28500, date: '2024-01-18',
                        children: [
                            { id: '002-01', name: 'Social Media', category: 'Marketing', value: 12000, date: '2024-01-19' },
                        ]
                    },
                    { id: '003', name: 'Customer Support', category: 'Service', value: 19800, date: '2024-01-25' },
                ]
            };

        default:
            return {};

    }
};


export const getDefaultStyle = () => ({
    showBorder: false,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    opacity: 100,
    accentColor: DEFAULT_COLORS.accent,
    backgroundColor: '#000000',
    textColor: '#ffffff',
    successColor: '#4ade80',
    dangerColor: '#f87171',
});
