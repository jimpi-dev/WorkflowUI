import type { NodeSpec } from '../types';

export const SwinIRLoaderSpec: NodeSpec = {
    classType: 'SwinIRLoader',
    fixedInputs: {
        model_name: {
            type: 'select',
            label: 'Upscale model',
            optionSource: 'upscale_models'
        }
    }
};
