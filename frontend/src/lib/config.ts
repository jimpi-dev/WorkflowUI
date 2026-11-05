export const appConfig: {
	ssr: boolean;
	backendUrl: string;
	version: string;
	appName: string;
	githubRepoUrl: string;
	presetsEnabled: boolean;
	genvaultEnabled: boolean;
} =
	typeof __APP_CONFIG__ !== 'undefined'
		? __APP_CONFIG__
		: {
				ssr: false,
				backendUrl: '',
				version: '1.0',
				appName: 'WorkflowUI by Jimpi',
				githubRepoUrl: 'https://github.com/jimpi-dev/WorkflowUI/',
				presetsEnabled: false,
				genvaultEnabled: true
			};

export function getApiBase(): string {
	const configured = (appConfig.backendUrl || '').trim();
	// When frontend and backend are served from the same origin (e.g. Docker image),
	// route API calls under /api to avoid clashes with SPA routes like /projects/*.
	return configured || '/api';
}

export const COMFYUI_MAX_SEED = 2 ** 50;
export const COMFYUI_INT_MAX = 2147483647;
