import type { NodeSpec } from '../types';

export const TextMultilineSpec: NodeSpec = {
    classType: 'Text Multiline',
    fixedInputs: {
        text: {
            type: 'text',
            label: 'Prompt'
        }
    }
};
