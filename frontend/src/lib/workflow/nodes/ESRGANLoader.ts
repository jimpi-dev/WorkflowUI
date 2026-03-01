import type { NodeSpec } from '../types';

export const ESRGANLoaderSpec: NodeSpec = {
    classType: 'ESRGANLoader',
    fixedInputs: {
        model_name: {
            type: 'select',
            label: 'Upscale model',
            optionSource: 'upscale_models'
        }
    }
};
