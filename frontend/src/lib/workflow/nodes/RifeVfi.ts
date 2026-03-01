import type { NodeSpec } from '../types';

export const RifeVfiSpec: NodeSpec = {
    classType: 'RIFE VFI',
    fixedInputs: {
        ckpt_name: {
            type: 'select',
            label: 'RIFE model',
            optionSource: 'rife_models'
        },
        multiplier: {
            type: 'number',
            label: 'Multiplier',
            min: 1,
            max: 16,
            step: 1
        },
        clear_cache_after_n_frames: {
            type: 'number',
            label: 'Clear cache after N frames',
            min: 1,
            max: 64
        },
        fast_mode: {
            type: 'boolean',
            label: 'Fast mode'
        },
        ensemble: {
            type: 'boolean',
            label: 'Ensemble'
        },
        scale_factor: {
            type: 'number',
            label: 'Scale factor',
            min: 0.25,
            max: 4,
            step: 0.25
        }
    }
};
