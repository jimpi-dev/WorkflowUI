import type { NodeSpec } from '../types';

export const SaveAudioMP3Spec: NodeSpec = {
    classType: 'SaveAudioMP3',
    fixedInputs: {
        filename_prefix: {
            type: 'text',
            label: 'Filename prefix'
        },
        quality: {
            type: 'select',
            label: 'Quality',
            options: ['V0', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8', 'V9']
        }
    },
    layout: {
        rows: [['filename_prefix', 'quality']]
    },
    outputs: {
        type: 'audio'
    }
};
