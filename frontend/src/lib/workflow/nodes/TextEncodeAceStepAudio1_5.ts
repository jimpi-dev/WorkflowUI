import type { NodeSpec } from '../types';

export const TextEncodeAceStepAudio1_5Spec: NodeSpec = {
    classType: 'TextEncodeAceStepAudio1.5',
    fixedInputs: {
        tags: {
            type: 'text',
            label: 'Tags / Description',
            multiline: true
        },
        lyrics: {
            type: 'text',
            label: 'Lyrics',
            multiline: true
        },
        seed: {
            type: 'seed',
            label: 'Seed'
        },
        bpm: {
            type: 'number',
            label: 'BPM',
            min: 1,
            max: 300
        },
        duration: {
            type: 'number',
            label: 'Duration (seconds)',
            min: 1,
            max: 600
        },
        timesignature: {
            type: 'select',
            label: 'Time signature',
            options: ['4', '3', '2', '6', '8']
        },
        language: {
            type: 'select',
            label: 'Language',
            options: ['en', 'zh', 'ja', 'de', 'fr', 'es', 'it', 'ko', 'pt', 'ru']
        },
        keyscale: {
            type: 'text',
            label: 'Key / Scale',
            multiline: false
        },
        cfg_scale: {
            type: 'number',
            label: 'CFG scale',
            min: 1,
            max: 10
        },
        temperature: {
            type: 'number',
            label: 'Temperature',
            min: 0.1,
            max: 2
        },
        top_p: {
            type: 'number',
            label: 'Top P',
            min: 0,
            max: 1
        },
        top_k: {
            type: 'number',
            label: 'Top K',
            min: 0,
            max: 100
        }
    },
    layout: {
        rows: [
            ['tags'],
            ['lyrics'],
            ['seed', 'bpm', 'duration'],
            ['timesignature', 'language', 'keyscale'],
            ['cfg_scale', 'temperature', 'top_p', 'top_k']
        ]
    }
};
