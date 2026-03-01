import type { NodeSpec } from '../types';

export const T5LoaderSpec: NodeSpec = {
    classType: 'T5Loader',
    fixedInputs: {
        t5_name: {
            type: 'select',
            label: 'T5 model',
            optionSource: 'clip_models'
        }
    }
};
