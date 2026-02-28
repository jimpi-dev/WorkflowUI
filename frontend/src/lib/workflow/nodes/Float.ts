import type { NodeSpec } from '../types';

export const FloatSpec: NodeSpec = {
    classType: 'Float',
    fixedInputs: {
        Number: {
            type: 'number',
            label: 'Value'
        }
    }
};
