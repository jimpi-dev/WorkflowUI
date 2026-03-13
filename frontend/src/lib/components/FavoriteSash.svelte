<script lang="ts">
	let {
		visible = false
	}: {
		visible?: boolean;
	} = $props();
</script>

{#if visible}
	<div class="favorite-sash" aria-hidden="true">
		<div class="favorite-sash-ribbon">
			<svg viewBox="0 0 24 24" aria-hidden="true">
				<path
					d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14 2 9.27l6.91-1.01L12 2z"
				/>
			</svg>
		</div>
	</div>
{/if}

<style>
	.favorite-sash {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		z-index: 3;
	}

	.favorite-sash-ribbon {
		position: absolute;
		top: 6px;
		left: -40px;
		width: 140px;
		padding: 8px 0;
		transform: rotate(-45deg);
		transform-origin: left top;
		background: linear-gradient(135deg, #f8e38a, #f0c96a, #d4af37);
		color: #1a1200;
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 0 10px rgba(0, 0, 0, 0.55);
		border-radius: 0 0 4px 0;
	}

	.favorite-sash-ribbon svg {
		width: 22px;
		height: 22px;
		fill: currentColor;
	}

	@media (max-width: 639px) {
		.favorite-sash-ribbon {
			top: 4px;
			left: -34px;
			width: 120px;
			padding: 6px 0;
		}
	}
</style>

