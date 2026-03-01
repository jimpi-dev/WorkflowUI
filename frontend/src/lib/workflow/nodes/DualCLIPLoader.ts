import type { NodeSpec } from '../types';

export const DualCLIPLoaderSpec: NodeSpec = {
    classType: 'DualCLIPLoader',
    fixedInputs: {
        clip_name1: {
            type: 'select',
            label: 'CLIP model 1',
            optionSource: 'clip_models'
        },
        clip_name2: {
            type: 'select',
            label: 'CLIP model 2',
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
            optionSource: 'devices'
        }
    }
};
