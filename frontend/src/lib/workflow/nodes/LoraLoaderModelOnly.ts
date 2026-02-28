import type { NodeSpec } from '../types';

export const LoraLoaderModelOnlySpec: NodeSpec = {
    classType: 'LoraLoaderModelOnly',
    headerBadge: 'LORA',
    fixedInputs: {
        lora_name: {
            type: 'select',
            label: 'LoRA',
            optionSource: 'loras'
        },
        strength_model: {
            type: 'number',
            label: 'Strength',
            min: 0,
            max: 2,
            step: 0.05,
            slider: true
        }
    }
};
