import type { NodeSpec } from '../types';

export const SD3CheckpointLoaderSpec: NodeSpec = {
    classType: 'SD3CheckpointLoader',
    headerBadge: 'CHECKPOINT',
    fixedInputs: {
        ckpt_name: {
            type: 'select',
            label: 'Checkpoint',
            optionSource: 'checkpoints'
        },
        shift: {
            type: 'number',
            label: 'Shift',
            min: 0,
            max: 10,
            step: 0.1,
            slider: true
        }
    }
};
