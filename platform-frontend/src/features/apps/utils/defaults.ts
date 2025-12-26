
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
        case 'metric':
            return { value: '2.4M', change: 12.5, trend: 'up', label: 'Revenue Q3' };
        case 'trend':
            return { value: '$145.2', change: 2.4, label: 'Stock Price' };
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
            return { score: 78, label: 'Health Score', subtext: 'Healthy' };
        case 'grade_card':
            return { grade: 'A-', label: 'Profitability', subtext: 'Top Tier' };
        case 'pie_chart':
            return [
                { label: 'Category A', value: 40, color: '#3b82f6' },
                { label: 'Category B', value: 30, color: '#10b981' },
                { label: 'Category C', value: 20, color: '#f59e0b' },
                { label: 'Category D', value: 10, color: '#ef4444' },
            ];
        case 'json':
            return {
                json: {
                    ticker: 'GOOGL',
                    metrics: { revenue: 282.8, net_income: 59.9, cash: 113.7 },
                    flags: ['undervalued', 'high_growth']
                }
            };
        case 'markdown':
            return { content: '# Hello Markdown\n\n- Item 1\n- Item 2\n\n> This is a quote.' };
        case 'header':
            return { text: 'Header' };
        case 'text':
            return { text: 'Basic paragraph text block. Select to edit.' };
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
