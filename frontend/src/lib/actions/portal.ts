import type { Action } from 'svelte/action';

/** Move node to `document.body` (or selector) so it escapes ancestor stacking / paint order (e.g. flex siblings). */
export const portal: Action<HTMLElement, string | undefined> = (node, selector = 'body') => {
	const target =
		typeof selector === 'string' ? (document.querySelector(selector) ?? document.body) : document.body;
	target.appendChild(node);
	return {
		destroy() {
			if (node.parentNode) node.parentNode.removeChild(node);
		}
	};
};
