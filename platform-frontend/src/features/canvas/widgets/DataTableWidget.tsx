import React, { useState, useMemo } from 'react';
import { useTheme } from '@/components/theme';

interface DataTableWidgetProps {
    title?: string;
    columns: { key: string; label: string; sortable?: boolean }[];
    rows: Record<string, any>[];
    pageSize?: number;
}

const DataTableWidget: React.FC<DataTableWidgetProps> = ({ title, columns = [], rows = [], pageSize = 10 }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const [sortKey, setSortKey] = useState<string | null>(null);
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
    const [page, setPage] = useState(0);
    const [filter, setFilter] = useState('');

    const filtered = useMemo(() => {
        if (!filter) return rows;
        const q = filter.toLowerCase();
        return rows.filter(row => columns.some(col => String(row[col.key] ?? '').toLowerCase().includes(q)));
    }, [rows, filter, columns]);

    const sorted = useMemo(() => {
        if (!sortKey) return filtered;
        return [...filtered].sort((a, b) => {
            const av = a[sortKey] ?? '', bv = b[sortKey] ?? '';
            const cmp = typeof av === 'number' ? av - (bv as number) : String(av).localeCompare(String(bv));
            return sortDir === 'asc' ? cmp : -cmp;
        });
    }, [filtered, sortKey, sortDir]);

    const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
    const paged = sorted.slice(page * pageSize, (page + 1) * pageSize);

    const handleSort = (key: string) => {
        if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortKey(key); setSortDir('asc'); }
    };

    return (
        <div className={`w-full rounded-lg border overflow-hidden ${isDark ? 'bg-gray-800/50 border-gray-700' : 'bg-white border-gray-200 shadow-sm'}`}>
            {(title || true) && (
                <div className={`flex items-center justify-between px-4 py-2 border-b ${isDark ? 'border-gray-700' : 'border-gray-200'}`}>
                    {title && <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{title}</h3>}
                    <input
                        type="text"
                        placeholder="Filter..."
                        value={filter}
                        onChange={e => { setFilter(e.target.value); setPage(0); }}
                        className={`text-xs px-2 py-1 rounded border outline-none w-40 ${isDark ? 'bg-gray-900 border-gray-600 text-gray-300 placeholder-gray-500' : 'bg-gray-50 border-gray-300 text-gray-700 placeholder-gray-400'}`}
                    />
                </div>
            )}
            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className={isDark ? 'bg-gray-900/50' : 'bg-gray-50'}>
                            {columns.map(col => (
                                <th
                                    key={col.key}
                                    onClick={() => col.sortable !== false && handleSort(col.key)}
                                    className={`px-3 py-2 text-left font-semibold uppercase tracking-wider cursor-pointer select-none ${isDark ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-800'}`}
                                >
                                    {col.label}
                                    {sortKey === col.key && (sortDir === 'asc' ? ' ↑' : ' ↓')}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {paged.map((row, i) => (
                            <tr key={i} className={`border-t ${isDark ? 'border-gray-700/50 hover:bg-gray-700/30' : 'border-gray-100 hover:bg-gray-50'}`}>
                                {columns.map(col => (
                                    <td key={col.key} className={`px-3 py-2 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                        {String(row[col.key] ?? '')}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        {paged.length === 0 && (
                            <tr><td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground italic">No data</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
            {totalPages > 1 && (
                <div className={`flex items-center justify-between px-4 py-2 border-t text-xs ${isDark ? 'border-gray-700 text-gray-400' : 'border-gray-200 text-gray-500'}`}>
                    <span>{sorted.length} rows</span>
                    <div className="flex items-center gap-2">
                        <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-2 py-0.5 rounded border border-current/20 disabled:opacity-30">Prev</button>
                        <span>{page + 1}/{totalPages}</span>
                        <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="px-2 py-0.5 rounded border border-current/20 disabled:opacity-30">Next</button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DataTableWidget;
