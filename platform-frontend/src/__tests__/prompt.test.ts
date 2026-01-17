
import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('IDE Agent Prompt Configuration', () => {
    const promptPath = path.resolve(__dirname, '../../../prompts/ide_agent_prompt.md');

    it('should exist', () => {
        expect(fs.existsSync(promptPath)).toBe(true);
    });

    it('should contain anti-redundancy instructions', () => {
        const content = fs.readFileSync(promptPath, 'utf-8');

        // precise phrases we added
        expect(content).toContain('NO REDUNDANCY');
        expect(content).toContain('Do NOT output the full code or file content in your text response');
        expect(content).toContain('Direct Tool Usage');
    });

    it('should prohibit interactive commands', () => {
        const content = fs.readFileSync(promptPath, 'utf-8');
        expect(content).toContain('Non-Interactive Shell');
        expect(content).toContain('NEVER run commands that wait for user input');
    });

    it('should enforce relative paths', () => {
        const content = fs.readFileSync(promptPath, 'utf-8');
        expect(content).toContain('Project Root');
        expect(content).toContain('relative to this root');
    });
});
