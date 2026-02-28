import type { NodeSpec } from '../types';

export const LoadImageSpec: NodeSpec = {
    classType: 'LoadImage',
    fixedInputs: {
        image: {
            type: 'image',
            label: 'Image'
        }
    }
};
