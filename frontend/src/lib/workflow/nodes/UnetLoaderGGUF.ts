import type { NodeSpec } from '../types';

export const UnetLoaderGGUFSpec: NodeSpec = {
    classType: 'UnetLoaderGGUF',
    fixedInputs: {
        unet_name: {
            type: 'select',
            label: 'UNet model (GGUF)',
            optionSource: 'unet_gguf_models'
        }
    }
};
