import type { NodeSpec } from '../types';

export const UNETLoaderSpec: NodeSpec = {
    classType: 'UNETLoader',
    fixedInputs: {
        unet_name: {
            type: 'select',
            label: 'UNet model',
            optionSource: 'checkpoints'
        },
        weight_dtype: {
            type: 'select',
            label: 'Weight dtype',
            options: ['default', 'fp8', 'fp16', 'bf16']
        }
    }
};
