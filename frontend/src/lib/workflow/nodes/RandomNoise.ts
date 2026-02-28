import type { NodeSpec } from '../types';

export const RandomNoiseSpec: NodeSpec = {
    classType: 'RandomNoise',
    fixedInputs: {
        noise_seed: {
            type: 'seed',
            label: 'Seed'
        }
    }
};
