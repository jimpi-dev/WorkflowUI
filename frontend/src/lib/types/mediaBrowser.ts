export type MediaBrowserSelection = {
    source: 'generation' | 'input';
    filename: string;
    runId?: string;
    outputIndex?: number;
    subfolder?: string;
    type?: string;
    projectId?: string;
    projectName?: string;
    appId?: string | null;
    appTitle?: string | null;
    createdAt?: number;
};

export type MediaBrowserItem = {
    run_id: string;
    run_group_id: string | null;
    project_id: string;
    project_name: string;
    app_id: string | null;
    app_title: string | null;
    created_at: number;
    output_index: number;
    filename: string;
    subfolder: string;
    type: string;
    source: 'generation' | 'input';
    is_favorite?: boolean;
};
