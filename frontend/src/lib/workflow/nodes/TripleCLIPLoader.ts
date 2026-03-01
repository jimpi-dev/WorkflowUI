import type { NodeSpec } from '../types';

export const TripleCLIPLoaderSpec: NodeSpec = {
    classType: 'TripleCLIPLoader',
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
        clip_name3: {
            type: 'select',
            label: 'CLIP model 3',
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
