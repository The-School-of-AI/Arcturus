import React from 'react';
import { BaseCard } from './BaseCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Calendar, ChevronDown } from 'lucide-react';

export const InputCard: React.FC<{ label?: string, placeholder?: string }> = ({ label = "Search Ticker", placeholder = "e.g. MSFT" }) => (
    <div className="p-3 bg-charcoal-800 rounded-lg border border-white/5 h-full flex flex-col justify-center gap-2">
        {label && <label className="text-[10px] uppercase font-bold text-muted-foreground">{label}</label>}
        <Input className="h-8 text-xs bg-black/40 border-white/10" placeholder={placeholder} />
    </div>
);

export const ActionButtonCard: React.FC<{ label?: string }> = ({ label = "Run Analysis" }) => (
    <div className="p-3 bg-charcoal-800 rounded-lg border border-white/5 h-full flex items-center justify-center">
        <Button className="w-full bg-primary text-primary-foreground hover:bg-primary/90 text-xs h-8">
            {label}
        </Button>
    </div>
);

export const SelectCard: React.FC<{ label?: string }> = ({ label = "Timeframe" }) => (
    <div className="p-3 bg-charcoal-800 rounded-lg border border-white/5 h-full flex flex-col justify-center gap-2">
        {label && <label className="text-[10px] uppercase font-bold text-muted-foreground">{label}</label>}
        <div className="relative">
            <select className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-foreground appearance-none focus:outline-none">
                <option>1 Month</option>
                <option>6 Months</option>
                <option>1 Year</option>
                <option>5 Years</option>
            </select>
            <ChevronDown className="absolute right-2 top-2.5 w-3 h-3 text-muted-foreground pointer-events-none" />
        </div>
    </div>
);

export const DateRangeCard: React.FC<{ label?: string }> = ({ label = "Date Range" }) => (
    <div className="p-3 bg-charcoal-800 rounded-lg border border-white/5 h-full flex flex-col justify-center gap-2">
        {label && <label className="text-[10px] uppercase font-bold text-muted-foreground">{label}</label>}
        <div className="flex items-center gap-2 p-2 bg-black/40 border border-white/10 rounded cursor-pointer hover:border-white/20 transition-colors">
            <Calendar className="w-3 h-3 text-primary" />
            <span className="text-[10px] text-foreground font-mono">2023-01-01</span>
            <span className="text-muted-foreground">→</span>
            <span className="text-[10px] text-foreground font-mono">Present</span>
        </div>
    </div>
);
