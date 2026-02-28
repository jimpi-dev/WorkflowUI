import type { NodeSpec } from '../types';

export const BasicSchedulerSpec: NodeSpec = {
    classType: 'BasicScheduler',
    fixedInputs: {
        scheduler: {
            type: 'select',
            label: 'Scheduler',
            optionSource: 'schedulers'
        },
        steps: {
            type: 'number',
            label: 'Steps',
            min: 1,
            max: 150,
            slider: true
        },
        denoise: {
            type: 'number',
            label: 'Denoise',
            min: 0,
            max: 1,
            step: 0.01,
            slider: true
        }
    }
};
