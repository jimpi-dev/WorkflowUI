import type { NodeSpec } from '../types';

export const RealESRGANLoaderSpec: NodeSpec = {
    classType: 'RealESRGANLoader',
    fixedInputs: {
        model_name: {
            type: 'select',
            label: 'Upscale model',
            optionSource: 'upscale_models'
        }
    }
};
