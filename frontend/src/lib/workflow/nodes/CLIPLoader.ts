import type { NodeSpec } from '../types';

export const CLIPLoaderSpec: NodeSpec = {
    classType: 'CLIPLoader',
    optionSourceForSelect: 'clip_models',
    fixedInputs: {
        clip_name: {
            type: 'select',
            label: 'CLIP model',
            optionSource: 'clip_models'
        },
        type: {
            type: 'select',
            label: 'Type',
            optionSource: 'clip_types'
        },
        device: {
            type: 'select',
            label: 'Device',
            options: ['default', 'cpu', 'cuda']
        }
    }
};
