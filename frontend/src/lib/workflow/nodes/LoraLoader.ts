import type { NodeSpec } from '../types';

export const LoraLoaderSpec: NodeSpec = {
    classType: 'LoraLoader',
    headerBadge: 'LORA',
    fixedInputs: {
        lora_name: {
            type: 'select',
            label: 'LoRA',
            optionSource: 'loras'
        },
        strength_model: {
            type: 'number',
            label: 'Strength (model)',
            min: -100,
            max: 100,
            step: 0.01,
            slider: true
        },
        strength_clip: {
            type: 'number',
            label: 'Strength (CLIP)',
            min: -100,
            max: 100,
            step: 0.01,
            slider: true
        }
    }
};
