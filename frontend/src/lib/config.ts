export const appConfig: {
	ssr: boolean;
	backendUrl: string;
	version: string;
	appName: string;
	githubRepoUrl: string;
	presetsEnabled: boolean;
} =
	typeof __APP_CONFIG__ !== 'undefined'
		? __APP_CONFIG__
		: {
				ssr: false,
				backendUrl: '',
				version: '1.0',
				appName: 'WorkflowUI by Jimpi',
				githubRepoUrl: 'https://github.com/jimpi-dev/WorkflowUI/',
				presetsEnabled: false
			};

export function getApiBase(): string {
	return appConfig.backendUrl || '';
}

export const COMFYUI_MAX_SEED = 2 ** 50;
/** ComfyUI INT widget max (e.g. WorkflowUILink input_number_*); seeds must be ≤ this. */
export const COMFYUI_INT_MAX = 2147483647;
