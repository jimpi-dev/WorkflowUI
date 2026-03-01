import type { NodeSpec } from '../types';

export const INTConstantSpec: NodeSpec = {
    classType: 'INTConstant',
    fixedInputs: {
        value: {
            type: 'number',
            label: 'Value'
        }
    }
};
