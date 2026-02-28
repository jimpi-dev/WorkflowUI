import type { NodeSpec } from '../types';

export const AudioQualityEnhancerSpec: NodeSpec = {
    classType: 'AudioQualityEnhancer',
    fixedInputs: {
        enhancement_level: {
            type: 'number',
            label: 'Enhancement level',
            min: 0,
            max: 3
        },
        use_source_separation: {
            type: 'select',
            label: 'Use source separation',
            options: ['true', 'false']
        },
        demucs_model: {
            type: 'text',
            label: 'Demucs model'
        },
        device: {
            type: 'select',
            label: 'Device',
            options: ['cuda', 'cpu', 'default']
        },
        vocals_enhance: {
            type: 'number',
            label: 'Vocals',
            min: 0,
            max: 1
        },
        drums_enhance: {
            type: 'number',
            label: 'Drums',
            min: 0,
            max: 1
        },
        bass_enhance: {
            type: 'number',
            label: 'Bass',
            min: 0,
            max: 1
        },
        other_enhance: {
            type: 'number',
            label: 'Other',
            min: 0,
            max: 1
        },
        clarity: {
            type: 'number',
            label: 'Clarity',
            min: 0,
            max: 1
        },
        dynamics: {
            type: 'number',
            label: 'Dynamics',
            min: 0,
            max: 1
        },
        warmth: {
            type: 'number',
            label: 'Warmth',
            min: 0,
            max: 1
        },
        air: {
            type: 'number',
            label: 'Air',
            min: 0,
            max: 1
        },
        dolby_effect: {
            type: 'number',
            label: 'Dolby effect',
            min: 0,
            max: 2
        },
        simple_mode: {
            type: 'select',
            label: 'Simple mode',
            options: ['Standard', 'Simple', 'Minimal']
        },
        apply_limiter: {
            type: 'select',
            label: 'Apply limiter',
            options: ['true', 'false']
        }
    },
    layout: {
        rows: [
            ['enhancement_level', 'use_source_separation', 'demucs_model', 'device'],
            ['vocals_enhance', 'drums_enhance', 'bass_enhance', 'other_enhance'],
            ['clarity', 'dynamics', 'warmth', 'air'],
            ['dolby_effect', 'simple_mode', 'apply_limiter']
        ]
    }
};
