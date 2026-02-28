import type { NodeSpec } from '../types';

export const PrimitiveStringMultilineSpec: NodeSpec = {
    classType: 'PrimitiveStringMultiline',
    fixedInputs: {
        value: {
            type: 'text',
            label: 'Prompt'
        }
    }
};
