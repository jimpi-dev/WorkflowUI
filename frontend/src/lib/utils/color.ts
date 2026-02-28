function hexToLuminance(hex: string): number {
	const clean = hex.replace(/^#/, '');
	let r: number, g: number, b: number;
	if (clean.length === 3) {
		r = parseInt(clean[0]! + clean[0], 16) / 255;
		g = parseInt(clean[1]! + clean[1], 16) / 255;
		b = parseInt(clean[2]! + clean[2], 16) / 255;
	} else {
		r = parseInt(clean.slice(0, 2), 16) / 255;
		g = parseInt(clean.slice(2, 4), 16) / 255;
		b = parseInt(clean.slice(4, 6), 16) / 255;
	}
	const linear = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
	return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

export function getContrastForeground(hex: string): 'light' | 'dark' {
	const luminance = hexToLuminance(hex);
	return luminance > 0.4 ? 'dark' : 'light';
}

export function gradientEndColor(hex: string): string {
	return hex;
}
