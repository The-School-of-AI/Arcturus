/**
 * ExcalidrawTransformer - Converts abstract A2UI drawing commands into 
 * valid ExcalidrawElement structures.
 */

import { getSceneVersion } from "@excalidraw/excalidraw";

export interface A2UIElement {
    id: string;
    type: 'text' | 'rectangle' | 'ellipse' | 'arrow' | 'line' | 'freedraw' | 'image';
    x: number;
    y: number;
    width?: number;
    height?: number;
    text?: string;
    fontSize?: number;
    strokeColor?: string;
    backgroundColor?: string;
    fillStyle?: 'solid' | 'hachure' | 'cross-hatch';
    strokeWidth?: number;
    strokeStyle?: 'solid' | 'dashed' | 'dotted';
    opacity?: number;
    points?: [number, number][];
    startArrowhead?: string | null;
    endArrowhead?: string | null;
    fontFamily?: number;
    textAlign?: 'left' | 'center' | 'right';
    verticalAlign?: 'top' | 'middle';
}

const DEFAULT_PROPS = {
    angle: 0,
    strokeColor: "#ffffff",
    backgroundColor: "transparent",
    fillStyle: "solid", // Better coverage than hachure
    strokeWidth: 1,
    strokeStyle: "solid",
    roughness: 0, // Solid shapes by default
    opacity: 100,
    strokeSharpness: "sharp",
    locked: false,
};

export function transformToExcalidraw(a2uiElements: A2UIElement[]): any[] {
    const elements = a2uiElements.map((el: any, index) => {
        // IDEMPOTENCY: If this is already a full Excalidraw element, return it as-is
        if (el.seed !== undefined && el.version !== undefined && el.type !== undefined) {
            return el;
        }

        // Create a stable seed based on the ID or index to prevent jitter
        const stableSeed = el.id ? Array.from(String(el.id)).reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0) : index;

        const common = {
            id: el.id || `el-${index}-${Date.now()}`,
            type: el.type,
            x: el.x,
            y: el.y,
            width: el.width || 0,
            height: el.height || 0,
            angle: 0,
            strokeColor: el.strokeColor || "#3b82f6",
            backgroundColor: el.backgroundColor || "transparent",
            fillStyle: el.fillStyle || "solid",
            strokeWidth: el.strokeWidth || 2,
            strokeStyle: el.strokeStyle || "solid",
            roughness: 0, // Cleaner rendering
            opacity: el.opacity || 100,
            groupIds: [],
            roundness: { type: 3 },
            seed: 12345 + (stableSeed % 10000),
            version: 1, // Will be updated by getSceneVersion
            versionNonce: 12345 + index,
            isDeleted: false,
            boundElements: null,
            updated: Date.now(),
            link: null,
            locked: false,
        };

        if (el.type === 'text') {
            return {
                ...common,
                text: el.text || "",
                fontSize: el.fontSize || 20,
                fontFamily: el.fontFamily || 1,
                textAlign: el.textAlign || "center",
                verticalAlign: el.verticalAlign || "middle",
                baseline: 18,
                containerId: null,
                originalText: el.text || "",
            };
        }

        if (el.type === 'arrow' || el.type === 'line' || el.type === 'freedraw') {
            const points = el.points || [[0, 0], [100, 100]];
            return {
                ...common,
                points: points.map((p: [number, number]) => [p[0], p[1]]),
                lastCommittedPoint: null,
                startBinding: null,
                endBinding: null,
                startArrowhead: el.startArrowhead !== undefined ? el.startArrowhead : (el.type === 'arrow' ? 'arrow' : null),
                endArrowhead: el.endArrowhead !== undefined ? el.endArrowhead : (el.type === 'arrow' ? 'arrow' : null),
            };
        }

        return common;
    });

    // CRITICAL: getSceneVersion expects transformed elements
    const sceneVersion = getSceneVersion(elements as any);
    return elements.map(el => ({ ...el, version: sceneVersion }));
}
