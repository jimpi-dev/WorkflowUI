import type { NodeSpec } from '../types';

export const ModelSamplingAuraFlowSpec: NodeSpec = {
    classType: 'ModelSamplingAuraFlow',
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
