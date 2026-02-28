import type { NodeSpec } from '../types';

export const KSamplerAdvancedSpec: NodeSpec = {
    classType: 'KSamplerAdvanced',
    headerBadge: 'SAMPLER',
    fixedInputs: {
        noise_seed: {
            type: 'seed',
            label: 'Seed'
        },
        steps: {
            type: 'number',
            label: 'Steps',
            min: 1,
            max: 150,
            slider: true
        },
        cfg: {
            type: 'number',
            label: 'CFG Scale',
            min: 1,
            max: 20,
            slider: true
        },
        sampler_name: {
            type: 'select',
            label: 'Sampler',
            optionSource: 'samplers'
        },
        scheduler: {
            type: 'select',
            label: 'Scheduler',
            optionSource: 'schedulers'
        }
    }
};
