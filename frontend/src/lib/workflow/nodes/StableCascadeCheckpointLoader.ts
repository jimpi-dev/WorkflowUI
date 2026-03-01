import type { NodeSpec } from '../types';

export const StableCascadeCheckpointLoaderSpec: NodeSpec = {
    classType: 'StableCascadeCheckpointLoader',
    headerBadge: 'CHECKPOINT',
    fixedInputs: {
        key_opt_b: {
            type: 'select',
            label: 'Stage B model',
            optionSource: 'stable_cascade_stage_b'
        },
        key_opt_c: {
            type: 'select',
            label: 'Stage C model',
            optionSource: 'stable_cascade_stage_c'
        },
        cache_mode: {
            type: 'select',
            label: 'Cache mode',
            options: ['none', 'stage_b', 'stage_c', 'all']
        }
    }
};
