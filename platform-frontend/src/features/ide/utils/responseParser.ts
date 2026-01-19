
export interface ToolCall {
    name: string;
    arguments: Record<string, any>;
}

export function parseToolCalls(content: string): ToolCall[] {
    // 1. Extract ALL code blocks and map them by optional ID (and keep track of latest)
    const blockMap = new Map<string, string>();
    let lastBlockContent: string | null = null;

    // Regex to find code blocks, optionally followed by <<ID>>
    // Group 1: Content inside backticks
    // Group 2: ID tag (optional, e.g. <<MyBlock>>)
    // Matches ```lang ... ``` <<ID>>
    const blockRegex = /```(?:\w+)?\s*([\s\S]*?)\s*```\s*(?:<<([A-Za-z0-9_]+)>>)?/g;

    let blockMatch;
    // Iterate through all blocks to build context
    while ((blockMatch = blockRegex.exec(content)) !== null) {
        const blockContent = blockMatch[1];
        const blockId = blockMatch[2]; // undefined if no tag

        // Only consider it a "code block" for injection if it doesn't look like a tool call response
        if (!blockContent.trim().startsWith('{') || !blockContent.includes('"tool"')) {
            lastBlockContent = blockContent;
            if (blockId) {
                blockMap.set(blockId, blockContent);
            }
        }
    }

    // 2. Extract Tool Calls
    // We iterate again to find the actual JSON blocks
    // Regex that handles any language identifier (json, tool_code, etc.) or none
    const toolRegex = /```\s*(?:\w+)?\s*([\s\S]*?)\s*```/g;
    const toolCalls: ToolCall[] = [];
    let match;

    while ((match = toolRegex.exec(content)) !== null) {
        try {
            const rawJson = match[1];
            const jsonCall = JSON.parse(rawJson);

            if (jsonCall.tool || jsonCall.name) {
                let args = jsonCall.args || jsonCall.arguments || {};

                // 3. Perform Substitution on String Arguments
                args = substituteArgs(args, blockMap, lastBlockContent);

                toolCalls.push({
                    name: jsonCall.tool || jsonCall.name,
                    arguments: args
                });
            }
        } catch (e) {
            // Ignore non-JSON blocks
        }
    }

    return toolCalls;
}

function substituteArgs(args: any, blockMap: Map<string, string>, lastBlock: string | null): any {
    if (typeof args === 'string') {
        const trimmed = args.trim();
        // Check for {{CODE_BLOCK}} or {{LAST_CODE_BLOCK}}
        if (trimmed === '{{CODE_BLOCK}}' || trimmed === '{{LAST_CODE_BLOCK}}') {
            return lastBlock || args;
        }

        // Check for {{ID}} regex match
        // Note: We use a regex to match the EXACT whole string for safety, or substring?
        // User asked for usage like content: "{{BLOCK}}"
        // If they embed it like "some text {{BLOCK}}", we should probably replace.
        // But for code injection, usually it's the WHOLE payload.
        // Let's do exact match OR regex replacement.

        // If exact match with ID
        const exactIdMatch = trimmed.match(/^{{([A-Za-z0-9_]+)}}$/);
        if (exactIdMatch) {
            const id = exactIdMatch[1];
            if (blockMap.has(id)) return blockMap.get(id);
        }

        return args;
    } else if (Array.isArray(args)) {
        return args.map(item => substituteArgs(item, blockMap, lastBlock));
    } else if (typeof args === 'object' && args !== null) {
        const newArgs: any = {};
        for (const key in args) {
            newArgs[key] = substituteArgs(args[key], blockMap, lastBlock);
        }
        return newArgs;
    }
    return args;
}
