import type { NodeSpec } from '../types';

export const SaveImageSpec: NodeSpec = {
    classType: 'SaveImage',
    fixedInputs: {
        filename_prefix: {
            type: 'text',
            label: 'Filename prefix',
            multiline: false
        }
    },
    outputs: {
        type: 'image'
    }
};
