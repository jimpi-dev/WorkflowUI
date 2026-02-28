import type { NodeSpec } from '../types';

export const SaveImageSpec: NodeSpec = {
    classType: 'SaveImage',
    fixedInputs: {
        filename_prefix: {
            type: 'text',
            label: 'Filename prefix'
        }
    },
    outputs: {
        type: 'image'
    }
};
