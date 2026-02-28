import type { NodeSpec } from '../types';

export const EasyIntSpec: NodeSpec = {
    classType: 'easy int',
    fixedInputs: {
        value: {
            type: 'number',
            label: 'Value'
        }
    }
};
