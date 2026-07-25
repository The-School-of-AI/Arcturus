import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

/** Parses a cron expression back into simple mode fields (if possible). */
function parseCronToSimple(cron: string): { frequency: string; time: string } | null {
    const parts = cron.trim().split(/\s+/);
    if (parts.length !== 5) return null;
    const [min, hr, day, mo, wkd] = parts;

    if (cron === '*/10 * * * *') return { frequency: 'every_10_min', time: '09:00' };
    if (cron === '*/30 * * * *') return { frequency: 'every_30_min', time: '09:00' };
    if (cron === '0 * * * *') return { frequency: 'hourly', time: '09:00' };
    if (day === '*' && mo === '*' && wkd === '*' && /^\d+$/.test(min) && /^\d+$/.test(hr)) {
        return { frequency: 'daily', time: `${hr.padStart(2, '0')}:${min.padStart(2, '0')}` };
    }
    if (day === '*' && mo === '*' && /^\d+$/.test(wkd) && /^\d+$/.test(min) && /^\d+$/.test(hr)) {
        return { frequency: 'weekly', time: `${hr.padStart(2, '0')}:${min.padStart(2, '0')}` };
    }
    return null; // Can't represent in simple mode
}

function generateCronFromSimple(frequency: string, time: string): string {
    if (frequency === 'every_10_min') return '*/10 * * * *';
    if (frequency === 'every_30_min') return '*/30 * * * *';
    if (frequency === 'hourly') return '0 * * * *';
    const [hours, mins] = time.split(':').map(Number);
    if (frequency === 'daily') return `${mins || 0} ${hours || 0} * * *`;
    if (frequency === 'weekly') return `${mins || 0} ${hours || 0} * * 1`;
    return '0 9 * * *';
}

export interface JobFormData {
    name: string;
    cron: string;
    query: string;
}

interface JobFormDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    submitLabel: string;
    initialValues?: { name: string; cron: string; query: string };
    onSubmit: (data: JobFormData) => Promise<void>;
}

export const JobFormDialog: React.FC<JobFormDialogProps> = ({
    open, onOpenChange, title, submitLabel, initialValues, onSubmit
}) => {
    const [name, setName] = useState('');
    const [cron, setCron] = useState('0 9 * * *');
    const [query, setQuery] = useState('');
    const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
    const [simpleFrequency, setSimpleFrequency] = useState('daily');
    const [simpleTime, setSimpleTime] = useState('09:00');
    const [saving, setSaving] = useState(false);

    // Reset form when dialog opens
    useEffect(() => {
        if (!open) return;
        if (initialValues) {
            setName(initialValues.name);
            setCron(initialValues.cron);
            setQuery(initialValues.query);
            // Try to parse the cron into simple mode
            const parsed = parseCronToSimple(initialValues.cron);
            if (parsed) {
                setMode('simple');
                setSimpleFrequency(parsed.frequency);
                setSimpleTime(parsed.time);
            } else {
                setMode('advanced');
            }
        } else {
            setName('');
            setCron('0 9 * * *');
            setQuery('');
            setMode('simple');
            setSimpleFrequency('daily');
            setSimpleTime('09:00');
        }
    }, [open, initialValues]);

    const currentCron = mode === 'simple' ? generateCronFromSimple(simpleFrequency, simpleTime) : cron;

    const handleSave = async () => {
        if (!name || !currentCron || !query) return;
        setSaving(true);
        try {
            await onSubmit({ name, cron: currentCron, query });
        } catch (e) {
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <label className="text-xs font-medium uppercase text-muted-foreground">Task Name</label>
                        <Input placeholder="e.g. Morning Briefing" value={name} onChange={(e) => setName(e.target.value)} />
                    </div>

                    <div className="flex items-center gap-4 border-b border-border/50 pb-2">
                        <button
                            onClick={() => setMode('simple')}
                            className={cn(
                                "text-xs font-bold uppercase transition-colors hover:text-foreground",
                                mode === 'simple' ? "text-info border-b-2 border-info" : "text-muted-foreground"
                            )}
                        >
                            Simple Mode
                        </button>
                        <button
                            onClick={() => setMode('advanced')}
                            className={cn(
                                "text-xs font-bold uppercase transition-colors hover:text-foreground",
                                mode === 'advanced' ? "text-info border-b-2 border-info" : "text-muted-foreground"
                            )}
                        >
                            Advanced (Cron)
                        </button>
                    </div>

                    {mode === 'simple' && (
                        <div className="space-y-3 bg-muted/20 p-3 rounded-md border border-border/30">
                            <div className="space-y-1">
                                <label className="text-xs font-medium uppercase text-muted-foreground">Frequency</label>
                                <select
                                    className="w-full bg-background/50 border border-border/30 rounded-md p-2 text-sm text-foreground focus:outline-none focus:border-info"
                                    value={simpleFrequency}
                                    onChange={(e) => setSimpleFrequency(e.target.value)}
                                >
                                    <option value="every_10_min">Every 10 Minutes</option>
                                    <option value="every_30_min">Every 30 Minutes</option>
                                    <option value="hourly">Hourly</option>
                                    <option value="daily">Daily</option>
                                    <option value="weekly">Weekly</option>
                                </select>
                            </div>
                            {(simpleFrequency === 'daily' || simpleFrequency === 'weekly') && (
                                <div className="space-y-1">
                                    <label className="text-xs font-medium uppercase text-muted-foreground">Time</label>
                                    <Input type="time" value={simpleTime} onChange={(e) => setSimpleTime(e.target.value)} className="bg-background/50" />
                                </div>
                            )}
                            <div className="text-xs text-muted-foreground pt-1">
                                Will run as: <code className="text-info">{currentCron}</code>
                            </div>
                        </div>
                    )}

                    {mode === 'advanced' && (
                        <div className="space-y-2">
                            <label className="text-xs font-medium uppercase text-muted-foreground">Cron Expression</label>
                            <div className="flex gap-2">
                                <Input placeholder="* * * * *" className="font-mono bg-muted/50" value={cron} onChange={(e) => setCron(e.target.value)} />
                                <div className="text-xs text-muted-foreground flex flex-col justify-center min-w-[100px]">
                                    <div>* * * * *</div>
                                    <div>min hr day mo wkd</div>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="text-xs font-medium uppercase text-muted-foreground">Agent Instructions</label>
                        <Input placeholder="What should the agent do?" value={query} onChange={(e) => setQuery(e.target.value)} />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button className="bg-info text-black hover:bg-info/90" disabled={saving} onClick={handleSave}>
                        {saving ? 'Saving...' : submitLabel}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
