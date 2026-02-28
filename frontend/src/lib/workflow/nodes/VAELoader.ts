import type { NodeSpec } from '../types';

export const VAELoaderSpec: NodeSpec = {
    classType: 'VAELoader',
    fixedInputs: {
        vae_name: {
            type: 'select',
            label: 'VAE',
            optionSource: 'vae_models'
        }
    }
};
