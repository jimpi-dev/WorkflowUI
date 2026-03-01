/// <reference types="vitest" />
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vite';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadPackageVersion(): string {
	try {
		const pkgPath = path.resolve(__dirname, 'package.json');
		const raw = readFileSync(pkgPath, 'utf-8');
		const pkg = JSON.parse(raw) as { version?: string };
		return typeof pkg.version === 'string' ? pkg.version : '1.0';
	} catch {
		return '1.0';
	}
}

function loadAppConfig(): {
	ssr: boolean;
	backendUrl: string;
	version: string;
	appName: string;
	githubRepoUrl: string;
	presetsEnabled: boolean;
} {
	const packageVersion = loadPackageVersion();
	const defaultConfig = {
		ssr: false,
		backendUrl: 'http://localhost:8000',
		version: packageVersion,
		appName: 'WorkflowUI by Jimpi',
		githubRepoUrl: 'https://github.com/jimpi-dev/WorkflowUI/',
		presetsEnabled: false
	};
	try {
		const configPath = path.resolve(__dirname, '../app.config.json');
		const raw = readFileSync(configPath, 'utf-8');
		const parsed = JSON.parse(raw) as Partial<{
			ssr: boolean;
			backendUrl: string;
			version: string;
			appName: string;
			githubRepoUrl: string;
			presetsEnabled: boolean;
		}>;
		return {
			ssr: parsed.ssr ?? defaultConfig.ssr,
			backendUrl:
				typeof process !== 'undefined' && process.env?.BACKEND_URL !== undefined
					? process.env.BACKEND_URL
					: typeof parsed.backendUrl === 'string'
						? parsed.backendUrl
						: defaultConfig.backendUrl,
			version: packageVersion,
			appName: typeof parsed.appName === 'string' ? parsed.appName : defaultConfig.appName,
			githubRepoUrl: typeof parsed.githubRepoUrl === 'string' ? parsed.githubRepoUrl : defaultConfig.githubRepoUrl,
			presetsEnabled: parsed.presetsEnabled ?? defaultConfig.presetsEnabled
		};
	} catch {
		return defaultConfig;
	}
}

const appConfig = loadAppConfig();
const proxyTarget = appConfig.backendUrl || 'http://localhost:8000';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	define: {
		__APP_CONFIG__: JSON.stringify(appConfig)
	},
	server: {
		proxy: {
			// Only proxy API paths that do NOT overlap with SvelteKit frontend routes.
			// /workflow uses bypass so /workflows (frontend route) is never proxied — avoids JSON on reload.
			'/workflow': {
				target: proxyTarget,
				bypass(req) {
					const path = req.url?.replace(/^https?:\/\/[^/]+/, '') ?? '';
					if (path === '/workflows' || path.startsWith('/workflows?') || path.startsWith('/workflows/')) return path;
				}
			},
			// /projects: proxy API (e.g. GET /projects, GET /projects/xxx/runs) but not browser document nav (Accept: text/html)
			'/projects': {
				target: proxyTarget,
				bypass(req) {
					const pathname = (req.url?.replace(/^https?:\/\/[^/]+/, '') ?? '').split('?')[0] ?? '';
					const wantsHtml = req.headers.accept?.includes('text/html');
					// Let SvelteKit serve the app for any /projects* route when the browser asks for HTML (reload/navigation)
					if (pathname === '/projects' || pathname.startsWith('/projects/')) {
						if (wantsHtml) return pathname;
					}
				}
			},
			'/runs': proxyTarget,
			'/object_info': proxyTarget,
			'/run': proxyTarget,
			'/outputs': proxyTarget,
			'/image': proxyTarget,
			'/loras': proxyTarget,
			'/checkpoints': proxyTarget,
			'/clip_models': proxyTarget,
			'/clip_types': proxyTarget,
			'/vae_models': proxyTarget,
			'/devices': proxyTarget,
			'/config': proxyTarget,
			// /apps: proxy API but not browser document nav (Accept: text/html) so /apps and /apps/create etc. serve the Svelte app
			'/apps': {
				target: proxyTarget,
				bypass(req) {
					const pathname = (req.url?.replace(/^https?:\/\/[^/]+/, '') ?? '').split('?')[0] ?? '';
					const wantsHtml = req.headers.accept?.includes('text/html');
					if (pathname === '/apps' || pathname.startsWith('/apps/')) {
						if (wantsHtml) return pathname;
					}
				}
			}
		}
	},
	test: {
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.{ts,svelte}'],
		globals: true,
		setupFiles: ['src/test/setup.ts'],
		coverage: {
			provider: 'v8',
			reporter: ['text', 'html'],
			include: ['src/lib/**/*.{ts,svelte}'],
			exclude: [
				'src/lib/**/*.test.{ts,svelte}',
				'src/lib/**/*.spec.{ts,svelte}',
				'src/test/**',
				'**/*.d.ts'
			]
		}
	}
});
