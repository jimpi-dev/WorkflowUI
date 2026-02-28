import type { NodeSpec } from '../types';

export const UpscaleModelLoaderSpec: NodeSpec = {
    classType: 'UpscaleModelLoader',
    fixedInputs: {
        model_name: {
            type: 'select',
            label: 'Upscale model',
            optionSource: 'upscale_models'
        }
    }
};
