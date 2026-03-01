import type { NodeSpec } from '../types';

export const CheckpointLoaderSpec: NodeSpec = {
    classType: 'CheckpointLoader',
    headerBadge: 'CHECKPOINT',
    fixedInputs: {
        ckpt_name: {
            type: 'select',
            label: 'Checkpoint',
            optionSource: 'checkpoints'
        }
    }
};
