import type { NodeSpec } from '../types';

export const Flux2SchedulerSpec: NodeSpec = {
    classType: 'Flux2Scheduler',
    fixedInputs: {
        steps: {
            type: 'number',
            label: 'Steps',
            min: 1,
            max: 150,
            slider: true
        }
    }
};
