import type { NodeSpec } from '../types';

export const DiffusionModelLoaderSpec: NodeSpec = {
    classType: 'DiffusionModelLoader',
    fixedInputs: {
        unet_name: {
            type: 'select',
            label: 'Diffusion model',
            optionSource: 'checkpoints'
        },
        weight_dtype: {
            type: 'select',
            label: 'Weight dtype',
            options: ['default', 'fp8', 'fp16', 'bf16']
        }
    }
};
