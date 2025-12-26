import React from 'react';
import { BaseCard } from './BaseCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Calendar, ChevronDown } from 'lucide-react';

interface ControlCardProps {
    label?: string;
    placeholder?: string;
    data?: any;
    config?: any;
    style?: any;
}

export const InputCard: React.FC<ControlCardProps> = ({
    label = "Text Input",
    placeholder = "e.g. MSFT",
    data = {},
    config = {},
    style = {}
}) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const displayPlaceholder = data.placeholder || placeholder;

    return (
        <div className="p-3 h-full flex flex-col justify-center gap-2">
            {showLabel && displayLabel && (
                <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>
            )}
            <Input
                className="h-8 text-xs bg-black/40 border-white/10"
                placeholder={displayPlaceholder}
                defaultValue={data.defaultValue || ''}
            />
        </div>
    );
};

export const ActionButtonCard: React.FC<ControlCardProps> = ({
    label = "Run Analysis",
    data = {},
    config = {},
    style = {}
}) => {
    const displayLabel = data.label || label;
    const accentColor = style.accentColor || '#eaff00';

    return (
        <div className="p-3 h-full flex items-center justify-center">
            <Button
                className="w-full text-xs h-8"
                style={{
                    backgroundColor: accentColor,
                    color: '#000'
                }}
            >
                {displayLabel}
            </Button>
        </div>
    );
};

export const SelectCard: React.FC<ControlCardProps> = ({
    label = "Dropdown",
    data = {},
    config = {},
    style = {}
}) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const options = data.options || ['1 Month', '6 Months', '1 Year', '5 Years'];
    const defaultValue = data.defaultValue || options[0];

    return (
        <div className="p-3 h-full flex flex-col justify-center gap-2">
            {showLabel && displayLabel && (
                <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>
            )}
            <div className="relative">
                <select
                    className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-foreground appearance-none focus:outline-none"
                    defaultValue={defaultValue}
                >
                    {options.map((opt: string) => (
                        <option key={opt} value={opt}>{opt}</option>
                    ))}
                </select>
                <ChevronDown className="absolute right-2 top-2.5 w-3 h-3 text-muted-foreground pointer-events-none" />
            </div>
        </div>
    );
};

export const DateRangeCard: React.FC<ControlCardProps> = ({
    label = "Date Range",
    data = {},
    config = {},
    style = {}
}) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const startDate = data.startDate || '2023-01-01';
    const endDate = data.endDate || 'Present';
    const accentColor = style.accentColor || '#eaff00';

    return (
        <div className="p-3 h-full flex flex-col justify-center gap-2">
            {showLabel && displayLabel && (
                <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>
            )}
            <div className="flex items-center gap-2 p-2 bg-black/40 border border-white/10 rounded cursor-pointer hover:border-white/20 transition-colors">
                <Calendar className="w-3 h-3" style={{ color: accentColor }} />
                <span className="text-[10px] text-foreground font-mono">{startDate}</span>
                <span className="text-muted-foreground">→</span>
                <span className="text-[10px] text-foreground font-mono">{endDate}</span>
            </div>
        </div>
    );
};
