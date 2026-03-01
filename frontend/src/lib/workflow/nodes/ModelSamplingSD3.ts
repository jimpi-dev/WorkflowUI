import type { NodeSpec } from '../types';

export const ModelSamplingSD3Spec: NodeSpec = {
    classType: 'ModelSamplingSD3',
    fixedInputs: {
        shift: {
            type: 'number',
            label: 'Shift',
            min: 0,
            max: 10,
            step: 0.1,
            slider: true
        }
    }
};
