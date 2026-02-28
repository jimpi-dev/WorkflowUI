export function portal(node: HTMLElement): { destroy(): void } {
	let cancelled = false;
	const id = requestAnimationFrame(() => {
		if (cancelled) return;
		document.body.appendChild(node);
	});
	return {
		destroy() {
			cancelled = true;
			cancelAnimationFrame(id);
			if (node.parentNode) node.parentNode.removeChild(node);
		}
	};
}
