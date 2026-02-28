import type { NodeSpec } from '../types';

export const KSamplerSelectSpec: NodeSpec = {
    classType: 'KSamplerSelect',
    fixedInputs: {
        sampler_name: {
            type: 'select',
            label: 'Sampler',
            optionSource: 'samplers'
        }
    }
};
