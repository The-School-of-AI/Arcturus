import React from 'react';
import { BaseCard } from './BaseCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Calendar, ChevronDown, Clock, Star, Plus, X } from 'lucide-react';
import { cn } from '@/lib/utils';

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

// --- NEW COMPONENT BLOCKS ---

export const CheckboxCard: React.FC<ControlCardProps> = ({ label = "Enable Feature", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const checked = data.value || data.checked || false;

    return (
        <div className="p-3 h-full flex items-center gap-3">
            <Checkbox checked={checked} className="border-white/20 data-[state=checked]:bg-neon-yellow data-[state=checked]:text-black" />
            {showLabel && <label className="text-xs font-medium cursor-pointer">{displayLabel}</label>}
        </div>
    );
};

export const SwitchCard: React.FC<ControlCardProps> = ({ label = "Toggle Mode", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const checked = data.value || data.checked || false;

    return (
        <div className="p-3 h-full flex items-center justify-between gap-2">
            {showLabel && <label className="text-xs font-medium">{displayLabel}</label>}
            <Switch checked={checked} className="data-[state=checked]:bg-neon-yellow" />
        </div>
    );
};

export const TextareaCard: React.FC<ControlCardProps> = ({ label = "Comments", placeholder = "Enter details...", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    return (
        <div className="p-3 h-full flex flex-col gap-2">
            {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
            <Textarea
                placeholder={data.placeholder || placeholder}
                className="resize-none bg-black/40 border-white/10 text-xs min-h-[60px]"
                defaultValue={data.value}
            />
        </div>
    );
};

export const RadioGroupCard: React.FC<ControlCardProps> = ({ label = "Select Option", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const options = data.options || ['Option A', 'Option B', 'Option C'];
    const selected = data.value || options[0];

    return (
        <div className="p-3 h-full flex flex-col gap-2">
            {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
            <div className="space-y-1.5">
                {options.map((opt: string) => (
                    <div key={opt} className="flex items-center gap-2">
                        <div className={cn(
                            "w-3 h-3 rounded-full border flex items-center justify-center",
                            selected === opt ? "border-neon-yellow" : "border-white/20"
                        )}>
                            {selected === opt && <div className="w-1.5 h-1.5 rounded-full bg-neon-yellow" />}
                        </div>
                        <span className="text-xs text-muted-foreground">{opt}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export const SliderCard: React.FC<ControlCardProps> = ({ label = "Volume", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const value = data.value || 50;
    const min = data.min || 0;
    const max = data.max || 100;

    return (
        <div className="p-3 h-full flex flex-col justify-center gap-2">
            <div className="flex justify-between">
                {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
                <span className="text-xs font-mono">{value}</span>
            </div>
            <input
                type="range"
                min={min}
                max={max}
                value={value}
                onChange={() => { }} // ReadOnly for mockup
                className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-neon-yellow"
            />
        </div>
    );
};

export const TagsInputCard: React.FC<ControlCardProps> = ({ label = "Tags", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const tags = data.value || ['React', 'TypeScript'];

    return (
        <div className="p-3 h-full flex flex-col gap-2">
            {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
            <div className="flex flex-wrap gap-1 mb-1">
                {tags.map((tag: string) => (
                    <span key={tag} className="px-1.5 py-0.5 rounded bg-primary/20 text-primary text-[10px] flex items-center gap-1 border border-primary/20">
                        {tag} <X className="w-2 h-2 opacity-50 cursor-pointer" />
                    </span>
                ))}
            </div>
            <Input className="h-7 text-xs bg-black/40 border-white/10" placeholder="Add tag..." />
        </div>
    );
};

export const NumberInputCard: React.FC<ControlCardProps> = ({ label = "Quantity", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    return (
        <div className="p-3 h-full flex flex-col justify-center gap-2">
            {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
            <Input
                type="number"
                className="h-8 text-xs bg-black/40 border-white/10 font-mono"
                defaultValue={data.value || 0}
                min={data.min}
                max={data.max}
            />
        </div>
    );
};

export const ColorPickerCard: React.FC<ControlCardProps> = ({ label = "Theme Color", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const value = data.value || "#eaff00";

    return (
        <div className="p-3 h-full flex items-center justify-between gap-2">
            {showLabel && <label className="text-xs font-medium text-muted-foreground">{displayLabel}</label>}
            <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-muted-foreground">{value}</span>
                <div
                    className="w-6 h-6 rounded border border-white/20"
                    style={{ backgroundColor: value }}
                />
            </div>
        </div>
    );
};

export const RatingCard: React.FC<ControlCardProps> = ({ label = "Rating", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const value = data.value || 3;
    const max = 5;

    return (
        <div className="p-3 h-full flex flex-col justify-center gap-1">
            {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
            <div className="flex gap-0.5">
                {Array.from({ length: max }).map((_, i) => (
                    <Star
                        key={i}
                        className={cn("w-4 h-4", i < value ? "fill-neon-yellow text-neon-yellow" : "text-muted-foreground/20")}
                    />
                ))}
            </div>
        </div>
    );
};

export const TimePickerCard: React.FC<ControlCardProps> = ({ label = "Time", data = {}, config = {} }) => {
    const showLabel = config.showLabel !== false;
    const displayLabel = data.label || label;
    const value = data.value || "12:00";

    return (
        <div className="p-3 h-full flex flex-col justify-center gap-2">
            {showLabel && <label className="text-[10px] uppercase font-bold text-muted-foreground">{displayLabel}</label>}
            <div className="relative">
                <Input
                    type="time"
                    className="h-8 text-xs bg-black/40 border-white/10 font-mono pl-8"
                    defaultValue={value}
                />
                <Clock className="absolute left-2.5 top-2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
            </div>
        </div>
    );
};
