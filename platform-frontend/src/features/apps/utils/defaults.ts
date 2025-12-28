
// Default colors for cards
export const DEFAULT_COLORS = {
    accent: '#eaff00',      // neon-yellow (keep fixed for now or make variable)
    background: 'hsl(var(--card))',
    text: 'hsl(var(--foreground))',
    secondary: 'hsl(var(--muted-foreground))',
    border: 'hsl(var(--border))',
    success: '#4ade80',
    danger: '#f87171',
};

// ... (keep middle content)

export const getDefaultStyle = () => ({
    showBorder: false,
    borderWidth: 2,
    borderColor: 'hsl(var(--border))',
    borderRadius: 12,
    opacity: 100,
    accentColor: DEFAULT_COLORS.accent,
    backgroundColor: 'hsl(var(--card))',
    textColor: 'hsl(var(--foreground))',
    successColor: '#4ade80',
    dangerColor: '#f87171',
});

export const COLOR_PRESETS = [
    { name: 'Neon Yellow', value: '#eaff00' },
    { name: 'Cyan', value: '#22d3ee' },
    { name: 'Green', value: '#4ade80' },
    { name: 'Purple', value: '#a855f7' },
    { name: 'Pink', value: '#ec4899' },
    { name: 'Red', value: '#ef4444' },
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

        // Quiz Blocks Default Data
        case 'quiz_mcq':
            return {
                question: 'What is the capital of France?',
                options: ['London', 'Berlin', 'Paris', 'Madrid'],
                correctAnswer: 2,
                score: 1,
                explanation: 'Paris is the capital and largest city of France.'
            };
        case 'quiz_tf':
            return {
                question: 'The Earth is flat.',
                correctAnswer: 'false',
                score: 1,
                explanation: 'The Earth is approximately spherical in shape.'
            };
        case 'quiz_multi':
            return {
                question: 'Which of the following are programming languages?',
                options: ['Python', 'HTML', 'JavaScript', 'CSS'],
                correctAnswers: [0, 2],
                score: 2,
                explanation: 'Python and JavaScript are programming languages. HTML and CSS are markup/styling languages.'
            };
        case 'quiz_rating':
            return {
                question: 'How would you rate this course?',
                maxStars: 5,
                score: 0
            };
        case 'quiz_likert':
            return {
                question: 'I found the material easy to understand.',
                scaleLabels: ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
                score: 0
            };
        case 'quiz_nps':
            return {
                question: 'How likely are you to recommend this to a friend?',
                score: 0
            };
        case 'quiz_ranking':
            return {
                question: 'Rank these planets by distance from the Sun (closest first):',
                items: ['Mars', 'Earth', 'Venus', 'Mercury'],
                correctOrder: [3, 2, 1, 0],
                score: 2
            };
        case 'quiz_fitb':
            return {
                sentence: 'The chemical symbol for water is ___.',
                correctAnswer: 'H2O',
                score: 1,
                explanation: 'Water is composed of two hydrogen atoms and one oxygen atom.'
            };
        case 'quiz_fitmb':
            return {
                passage: 'The ___1___ is the largest organ in the human body. The ___2___ pumps blood throughout the body.',
                correctAnswers: ['skin', 'heart'],
                score: 2
            };
        case 'quiz_number':
            return {
                question: 'What is 15 × 8?',
                correctAnswer: 120,
                tolerance: 0,
                score: 1
            };
        case 'quiz_formula':
            return {
                question: 'Calculate the area of a circle with radius r.',
                formula: 'A = πr²',
                variables: { r: 5 },
                correctAnswer: 78.54,
                score: 2
            };
        case 'quiz_date':
            return {
                question: 'When did World War II end?',
                correctAnswer: '1945-09-02',
                score: 1
            };
        case 'quiz_essay':
            return {
                question: 'Discuss the causes and effects of climate change.',
                minWords: 100,
                maxWords: 500,
                score: 10,
                rubric: 'Clear thesis, supporting evidence, proper structure, grammar.'
            };
        case 'quiz_match':
            return {
                question: 'Match each country with its capital:',
                leftItems: ['France', 'Japan', 'Brazil', 'Egypt'],
                rightItems: ['Tokyo', 'Paris', 'Cairo', 'Brasília'],
                correctPairs: { '0': '1', '1': '0', '2': '3', '3': '2' },
                score: 4
            };
        case 'quiz_dropdown':
            return {
                content: {
                    text: 'The {0} is the powerhouse of the cell. DNA is stored in the {1}.',
                    dropdowns: [
                        { options: ['Nucleus', 'Mitochondria', 'Ribosome'], correct: 1 },
                        { options: ['Cytoplasm', 'Nucleus', 'Cell Wall'], correct: 1 }
                    ]
                },
                score: 2
            };
        case 'quiz_code':
            return {
                question: 'Write a function that returns the sum of two numbers.',
                starterCode: 'def add(a, b):\n    # Your code here\n    pass',
                language: 'python',
                testCases: [
                    { input: [2, 3], expected: 5 },
                    { input: [-1, 1], expected: 0 }
                ],
                score: 5
            };
        case 'quiz_upload':
            return {
                question: 'Upload your completed assignment (PDF or DOCX).',
                allowedTypes: ['.pdf', '.docx', '.doc'],
                maxSize: 10,
                score: 10
            };
        case 'quiz_image':
            return {
                question: 'Click on the brain in this image.',
                imageUrl: '',
                hotspots: [{ x: 50, y: 30, width: 20, height: 20, label: 'Brain' }],
                score: 1
            };
        case 'quiz_text':
            return {
                content: '## Instructions\n\nRead the following passage carefully before answering the questions below.'
            };
        case 'quiz_section':
            return {
                title: 'Section 1: Multiple Choice',
                description: 'Answer all questions in this section. Each question is worth 1 point.'
            };
        case 'quiz_media':
            return {
                question: 'Watch the video and answer the question below.',
                mediaUrl: '',
                mediaType: 'video',
                score: 2
            };
        case 'quiz_branch':
            return {
                question: 'Did you complete the prerequisite course?',
                branchLogic: {
                    'yes': 'continue',
                    'no': 'skip_to_section_2'
                }
            };
        case 'quiz_ai':
            return {
                question: 'Explain the concept of machine learning in your own words.',
                rubric: {
                    criteria: [
                        { name: 'Understanding', weight: 40, description: 'Shows clear understanding of ML concepts' },
                        { name: 'Examples', weight: 30, description: 'Provides relevant examples' },
                        { name: 'Clarity', weight: 30, description: 'Well-structured and clear explanation' }
                    ]
                },
                score: 10
            };

        default:
            return {};

    }
};




// Typical usage descriptions for all component types
export const COMPONENT_USAGE: Record<string, string> = {
    // Basics
    metric: 'Display key performance indicators like revenue, users, or any single important value with optional trend indicator.',
    trend: 'Show stock prices, currency rates, or any value that changes over time with directional trend.',
    header: 'Section headers to organize and label different areas of your dashboard.',
    text: 'Add descriptive text, notes, or explanations anywhere in your dashboard.',
    markdown: 'Rich formatted content with headings, lists, links, and code blocks.',
    image: 'Display logos, banners, product photos, or any visual content.',
    divider: 'Visual separator to create clear sections between groups of components.',

    // Charts & Data
    line_chart: 'Visualize trends over time - perfect for revenue, user growth, or any time-series data.',
    bar_chart: 'Compare values across categories - ideal for sales by region, product comparisons.',
    area_chart: 'Show cumulative totals or volume over time with filled visual areas.',
    pie_chart: 'Display proportions and percentages - market share, budget allocation, demographics.',
    sankey: 'Visualize flow and conversions - user journeys, budget flows, process funnels.',
    scatter: 'Show correlations between two variables - pricing vs sales, height vs weight.',
    heatmap: 'Display intensity patterns - activity by day/hour, correlation matrices.',
    table: 'Structured data display with rows and columns - reports, lists, detailed data.',

    // Finance
    profile: 'Company profile with logo, ticker, sector info - perfect for stock analysis dashboards.',
    valuation: 'Fair value gauge showing if an asset is over/undervalued with price comparison.',
    score_card: 'Circular score indicator (0-100) - quality scores, ratings, health metrics.',
    grade_card: 'Letter grade display (A+ to F) - ratings, performance grades, quality tiers.',
    peer_table: 'Side-by-side comparison of companies or products with key metrics.',
    ratios: 'Financial ratios grid - P/E, ROE, debt ratios with status indicators.',
    cash_flow: 'Operating, investing, and financing cash flow breakdown.',
    balance_sheet: 'Assets, liabilities, and equity visualization.',
    income_stmt: 'Revenue to net income waterfall breakdown.',
    summary: 'Executive summary with key points and highlights.',

    // Controls
    button: 'Trigger actions, run analyses, or navigate to other pages.',
    input: 'Text input for user data entry - search, filters, form fields.',
    select: 'Dropdown selection from predefined options.',
    checkbox: 'Toggle options on/off - filters, settings, selections.',
    radio: 'Single selection from multiple exclusive options.',
    slider: 'Numeric value selection with a draggable range control.',
    date_picker: 'Select dates or date ranges for filtering data.',

    // Dev & Feed
    feed: 'RSS/JSON feed display - news, updates, notifications.',
    log: 'System logs with color-coded levels - debugging, monitoring.',
    code: 'Syntax-highlighted code display - snippets, examples, scripts.',
    json: 'Interactive JSON viewer with collapsible nodes - API responses, configs.',

    // Blocks
    stats_trending: 'Trending stats list with value changes - financial metrics, KPIs.',
    stats_grid: 'Grid of statistics with trend indicators - dashboard overview.',
    stats_status: 'Status indicators with health badges - system monitoring.',
    stats_links: 'Clickable stat links - navigation, quick access metrics.',
    simple_table: 'Minimal table with status indicators - task lists, status tracking.',
    stats_01: 'Horizontal stat cards with change indicators.',
    usage_stats: 'Usage meters with progress bars - quotas, limits, consumption.',
    storage_card: 'Storage usage donut chart with segment breakdown.',
    accordion_table: 'Expandable hierarchical data table - nested data, categories.',
};
