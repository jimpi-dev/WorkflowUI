import adapterAuto from '@sveltejs/adapter-auto';
import adapterStatic from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// Use adapter-static for Docker/production static build (ADAPTER_STATIC=1); otherwise adapter-auto for dev.
		adapter:
			process.env.ADAPTER_STATIC === '1'
				? adapterStatic({ pages: 'build', assets: 'build', fallback: 'index.html', precompress: false, strict: false })
				: adapterAuto()
	}
};

export default config;
