import type { NodeSpec } from '../types';

export const CLIPTextEncodeSpec: NodeSpec = {
    classType: 'CLIPTextEncode',
    fixedInputs: {
        text: {
            type: 'text',
            label: 'Prompt'
        }
    }
};
