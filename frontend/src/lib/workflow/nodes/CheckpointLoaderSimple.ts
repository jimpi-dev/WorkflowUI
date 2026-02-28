import type { NodeSpec } from '../types';

export const CheckpointLoaderSimpleSpec: NodeSpec = {
    classType: 'CheckpointLoaderSimple',
    headerBadge: 'CHECKPOINT',
    fixedInputs: {
        ckpt_name: {
            type: 'select',
            label: 'Checkpoint',
            optionSource: 'checkpoints'
        }
    }
};
