import type { NodeSpec } from '../types';

export const FluxCheckpointLoaderSpec: NodeSpec = {
    classType: 'FluxCheckpointLoader',
    headerBadge: 'CHECKPOINT',
    fixedInputs: {
        ckpt_name: {
            type: 'select',
            label: 'Checkpoint',
            optionSource: 'checkpoints'
        }
    }
};
