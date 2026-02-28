import type { NodeSpec } from '../types';

export const CRLatentInputSwitchSpec: NodeSpec = {
    classType: 'CR Latent Input Switch',
    fixedInputs: {
        Input: {
            type: 'number',
            label: 'Input',
            min: 1,
            max: 2,
            step: 1
        }
    }
};
