/**
 * Shared Gemini model definitions — used by SettingsPage & IdeAgentPanel.
 * When the dynamic /settings/gemini/models endpoint succeeds, its results
 * replace this list at runtime. This is the offline / auth-failure fallback.
 */

export interface GeminiModel {
    value: string;
    label: string;
    description: string;
}

export const GEMINI_MODELS_FALLBACK: GeminiModel[] = [
    // Gemini 3.x
    { value: 'gemini-3.1-pro-preview',          label: 'Gemini 3.1 Pro',             description: 'Latest flagship model' },
    { value: 'gemini-3.1-flash-lite-preview',    label: 'Gemini 3.1 Flash Lite',      description: 'Latest fast & cheap' },
    { value: 'gemini-3-pro-preview',             label: 'Gemini 3 Pro',               description: 'Advanced multimodal' },
    { value: 'gemini-3-flash-preview',           label: 'Gemini 3 Flash',             description: 'Fast next-gen' },
    // Gemini 2.5
    { value: 'gemini-2.5-pro',                  label: 'Gemini 2.5 Pro',             description: 'Advanced reasoning (GA)' },
    { value: 'gemini-2.5-flash',                label: 'Gemini 2.5 Flash',           description: 'Fast, grounded (GA)' },
    { value: 'gemini-2.5-flash-lite',           label: 'Gemini 2.5 Flash Lite',      description: 'Lowest cost' },
    // Gemini 2.0
    { value: 'gemini-2.0-flash-001',            label: 'Gemini 2.0 Flash',           description: 'Stable workhorse' },
    { value: 'gemini-2.0-flash-lite-001',       label: 'Gemini 2.0 Flash Lite',      description: 'Budget option' },
];
