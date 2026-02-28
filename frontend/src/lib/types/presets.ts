export type AppPreset = {
	id: string;
	app_id: string;
	name: string;
	description: string | null;
	keys: string[];
	values: Record<string, unknown>;
	created_at: number;
};
