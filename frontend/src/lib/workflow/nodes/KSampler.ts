import type { NodeSpec } from '../types';

export const KSamplerSpec: NodeSpec = {
    classType: 'KSampler',
    headerBadge: 'SAMPLER',
    fixedInputs: {
        seed: {
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
        }
    }
};
