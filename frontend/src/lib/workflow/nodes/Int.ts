import type { NodeSpec } from '../types';

export const IntSpec: NodeSpec = {
    classType: 'Int',
    fixedInputs: {
        Number: {
            type: 'number',
            label: 'Value'
        }
    }
};
