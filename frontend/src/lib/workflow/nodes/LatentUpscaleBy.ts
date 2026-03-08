import type { NodeSpec } from '../types';

export const LatentUpscaleBySpec: NodeSpec = {
    classType: 'LatentUpscaleBy',
    fixedInputs: {
        upscale_method: {
            type: 'select',
            label: 'Upscale method',
            optionSource: 'upscale_methods'
        },
        scale_by: {
            type: 'number',
            label: 'Scale by',
            min: 0.25,
            max: 4,
            step: 0.25,
            slider: true
        }
    }
};
