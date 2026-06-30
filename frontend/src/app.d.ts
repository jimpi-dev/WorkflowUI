declare global {
	namespace App {
	}

	const __APP_CONFIG__: {
		ssr: boolean;
		backendUrl: string;
		version: string;
		appName: string;
		githubRepoUrl: string;
		presetsEnabled: boolean;
		genvaultEnabled: boolean;
	};
}

export {};