import type { NodeSpec } from '../types';

export const LycorisLoaderSpec: NodeSpec = {
    classType: 'LycorisLoaderNode',
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
        },
        lycoris_type: {
            type: 'select',
            label: 'LyCORIS type',
            optionSource: 'lycoris_types'
        }
    }
};
