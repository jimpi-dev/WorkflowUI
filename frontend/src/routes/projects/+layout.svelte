<script lang="ts">
	let { children } = $props();
</script>

<div class="projects-layout">
	{@render children()}
</div>

<style>
	.projects-layout {
		display: flex;
		flex-direction: column;
		min-height: 0;
		flex: 1;
	}
</style>
