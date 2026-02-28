import type { NodeSpec } from '../types';

export const EmptyAceStep1_5LatentAudioSpec: NodeSpec = {
    classType: 'EmptyAceStep1.5LatentAudio',
    fixedInputs: {
        seconds: {
            type: 'number',
            label: 'Duration (seconds)',
            min: 1,
            max: 600
        },
        batch_size: {
            type: 'number',
            label: 'Batch size',
            min: 1,
            max: 64
        }
    },
    layout: {
        rows: [['seconds', 'batch_size']]
    },
    headerBadge: 'AUDIO LATENT'
};
