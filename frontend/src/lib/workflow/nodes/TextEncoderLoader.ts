import type { NodeSpec } from '../types';

export const TextEncoderLoaderSpec: NodeSpec = {
    classType: 'TextEncoderLoader',
    fixedInputs: {
        name: {
            type: 'select',
            label: 'Text encoder model',
            optionSource: 'clip_models'
        }
    }
};
