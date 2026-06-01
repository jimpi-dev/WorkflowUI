<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount, onDestroy, tick } from 'svelte';

export type LightboxItem = {
		id: string;
		url: string;
		thumbnailUrl?: string;
		filename?: string;
		mediaType?: 'image' | 'video' | 'audio';
		remote_deleted?: boolean;
		hasLocal?: boolean;
		hasRemote?: boolean;
		seed?: number;
		executionTimeSec?: number;
		outputIndex?: number;
		runId?: string;
		backendRunId?: string;
	};

	type VideoFitMode = 'fit' | 'actual';
	type ImageFitMode = VideoFitMode;
	type VideoLoopMode = 'single' | 'playlist';
	type SlideshowSpeed = 'slow' | 'medium' | 'fast';

	const SLIDESHOW_INTERVALS: Record<SlideshowSpeed, number> = {
		slow: 5000,
		medium: 3000,
		fast: 1500
	};

	const ZOOM_MIN = 0.1;
	const ZOOM_MAX = 6;
	const SWIPE_THRESHOLD_PX = 50;

let {
		open = false,
		items = [],
		index = 0,
		onIndexChange = () => {},
		onClose = () => {},
		onDownload = undefined as ((item: LightboxItem) => void | Promise<void>) | undefined,
		onMetadata = undefined as ((item: LightboxItem) => void) | undefined,
		onSendToApp = undefined as ((item: LightboxItem) => void) | undefined,
		onSendToVault = undefined as ((item: LightboxItem) => void) | undefined,
		isInVault = undefined as ((item: LightboxItem) => boolean) | undefined,
		isSendingToVault = undefined as ((item: LightboxItem) => boolean) | undefined,
		onToggleFavorite = undefined as ((item: LightboxItem) => void) | undefined,
		isFavorite = undefined as ((item: LightboxItem) => boolean) | undefined,
		onToggleSelection = undefined as ((item: LightboxItem) => void) | undefined,
		isSelected = undefined as ((item: LightboxItem) => boolean) | undefined,
		onDeleteLocal = undefined as ((item: LightboxItem) => void) | undefined,
		onDeleteRemote = undefined as ((item: LightboxItem) => void) | undefined,
		onDeleteBoth = undefined as ((item: LightboxItem) => void) | undefined,
		showCloseLabel = true,
		ariaTitle = 'Media viewer'
	}: {
		open?: boolean;
		items?: LightboxItem[];
		index?: number;
		onIndexChange?: (index: number) => void;
		onClose?: () => void;
		onDownload?: (item: LightboxItem) => void | Promise<void>;
		onMetadata?: (item: LightboxItem) => void;
		onSendToApp?: (item: LightboxItem) => void;
		onSendToVault?: (item: LightboxItem) => void;
		isInVault?: (item: LightboxItem) => boolean;
		isSendingToVault?: (item: LightboxItem) => boolean;
		onToggleFavorite?: (item: LightboxItem) => void;
		isFavorite?: (item: LightboxItem) => boolean;
		onToggleSelection?: (item: LightboxItem) => void;
		isSelected?: (item: LightboxItem) => boolean;
		onDeleteLocal?: (item: LightboxItem) => void;
		onDeleteRemote?: (item: LightboxItem) => void;
		onDeleteBoth?: (item: LightboxItem) => void;
		showCloseLabel?: boolean;
		ariaTitle?: string;
	} = $props();

	let fitToScreen = $state(true);
	let zoom = $state(1);
	let zoomMode = $state(false);
	let isPanning = $state(false);
	let baseWidth = $state(0);
	let lightboxRootEl = $state<HTMLDivElement | null>(null);
	let fullscreenActive = $state(false);
	let scrollEl = $state<HTMLDivElement | null>(null);
	let imgEl = $state<HTMLImageElement | null>(null);
	let videoEl = $state<HTMLVideoElement | null>(null);
	let audioEl = $state<HTMLAudioElement | null>(null);
	let carouselTrackEl = $state<HTMLDivElement | null>(null);

	let loadFailed = $state(false);
	let loadFailedCarousel = $state<Set<string>>(new Set());
	let loadedCarouselThumbs = $state<Set<string>>(new Set());

	let zoomHintVisible = $state(false);
	let zoomHintTimeoutId: ReturnType<typeof setTimeout> | undefined;
	function dismissZoomHint() {
		zoomHintVisible = false;
		if (zoomHintTimeoutId != null) {
			clearTimeout(zoomHintTimeoutId);
			zoomHintTimeoutId = undefined;
		}
		if (browser) sessionStorage.setItem('workflowui_lightbox_zoom_hint_seen', '1');
	}

	let panStartX = 0;
	let panStartY = 0;
	let panStartScrollLeft = 0;
	let panStartScrollTop = 0;
	let touchStartX = 0;
	let touchSwipeHandled = false;

	// Playback options (with optional session persistence)
	function getStoredVideoFit(): VideoFitMode {
		if (!browser) return 'fit';
		return (sessionStorage.getItem('workflowui_lightbox_video_fit') as VideoFitMode) || 'fit';
	}
	function getStoredImageFit(): ImageFitMode {
		if (!browser) return 'fit';
		return (sessionStorage.getItem('workflowui_lightbox_image_fit') as ImageFitMode) || 'fit';
	}
	function getStoredVideoLoop(): VideoLoopMode {
		if (!browser) return 'single';
		return (sessionStorage.getItem('workflowui_lightbox_video_loop') as VideoLoopMode) || 'single';
	}
	function getStoredAudioPlaylist(): boolean {
		if (!browser) return false;
		return sessionStorage.getItem('workflowui_lightbox_audio_playlist') === '1';
	}
	function getStoredSlideshowSpeed(): SlideshowSpeed {
		if (!browser) return 'medium';
		return (sessionStorage.getItem('workflowui_lightbox_slideshow_speed') as SlideshowSpeed) || 'medium';
	}

	let videoFitMode = $state<VideoFitMode>(getStoredVideoFit());
	let imageFitMode = $state<ImageFitMode>(getStoredImageFit());
	let videoLoopMode = $state<VideoLoopMode>(getStoredVideoLoop());
	let audioPlaylistMode = $state(getStoredAudioPlaylist());
	let slideshowActive = $state(false);
	let slideshowSpeed = $state<SlideshowSpeed>(getStoredSlideshowSpeed());
	let slideshowTimerId: ReturnType<typeof setTimeout> | undefined;

	function persistVideoFit(v: VideoFitMode) {
		videoFitMode = v;
		if (browser) sessionStorage.setItem('workflowui_lightbox_video_fit', v);
	}
	function persistImageFit(v: ImageFitMode) {
		dismissZoomHint();
		if (zoomMode) {
			zoomMode = false;
			zoom = 1;
			isPanning = false;
			fitToScreen = true;
		}
		imageFitMode = v;
		if (browser) sessionStorage.setItem('workflowui_lightbox_image_fit', v);
		resetScroll();
	}
	function persistVideoLoop(v: VideoLoopMode) {
		videoLoopMode = v;
		if (browser) sessionStorage.setItem('workflowui_lightbox_video_loop', v);
	}
	function persistAudioPlaylist(v: boolean) {
		audioPlaylistMode = v;
		if (browser) sessionStorage.setItem('workflowui_lightbox_audio_playlist', v ? '1' : '0');
	}
	function persistSlideshowSpeed(v: SlideshowSpeed) {
		slideshowSpeed = v;
		if (browser) sessionStorage.setItem('workflowui_lightbox_slideshow_speed', v);
	}

	let downloading = $state(false);
	async function handleDownload(item: LightboxItem) {
		if (downloading || !onDownload) return;
		downloading = true;
		try {
			await onDownload(item);
		} finally {
			downloading = false;
		}
	}

	let currentItem = $derived(items[index] ?? null);
	let isVideo = $derived(currentItem?.mediaType === 'video');
	let isAudio = $derived(currentItem?.mediaType === 'audio');
	let isImage = $derived(currentItem?.mediaType === 'image' || (currentItem?.mediaType == null && currentItem));

	function resetScroll() {
		if (scrollEl) {
			scrollEl.scrollLeft = 0;
			scrollEl.scrollTop = 0;
		}
	}

	function goNext() {
		if (!items.length) return;
		loadFailed = false;
		onIndexChange((index + 1) % items.length);
		zoom = 1;
		resetScroll();
		stopSlideshowTimer();
	}

	function goPrev() {
		if (!items.length) return;
		loadFailed = false;
		onIndexChange((index - 1 + items.length) % items.length);
		zoom = 1;
		resetScroll();
		stopSlideshowTimer();
	}

	function goTo(i: number) {
		if (i === index || i < 0 || i >= items.length) return;
		loadFailed = false;
		onIndexChange(i);
		zoom = 1;
		resetScroll();
		stopSlideshowTimer();
	}

	async function exitFullscreenIfNeeded() {
		if (!browser) return;
		const doc = document as Document & { webkitFullscreenElement?: Element | null };
		const fsEl = document.fullscreenElement ?? doc.webkitFullscreenElement;
		if (!fsEl) return;
		try {
			if (document.exitFullscreen) await document.exitFullscreen();
			else if ((document as Document & { webkitExitFullscreen?: () => Promise<void> }).webkitExitFullscreen) {
				await (document as Document & { webkitExitFullscreen: () => Promise<void> }).webkitExitFullscreen();
			}
		} catch {
			/* ignore */
		}
	}

	async function handleClose() {
		stopSlideshowTimer();
		slideshowActive = false;
		await exitFullscreenIfNeeded();
		onClose();
	}

	async function toggleLightboxFullscreen() {
		if (!browser || !lightboxRootEl) return;
		const el = lightboxRootEl as HTMLDivElement & {
			webkitRequestFullscreen?: () => Promise<void>;
		};
		try {
			if (document.fullscreenElement ?? (document as Document & { webkitFullscreenElement?: Element }).webkitFullscreenElement) {
				await exitFullscreenIfNeeded();
			} else if (el.requestFullscreen) {
				await el.requestFullscreen();
			} else if (el.webkitRequestFullscreen) {
				await el.webkitRequestFullscreen();
			}
		} catch {
			/* unsupported or blocked */
		}
	}

	function syncFullscreenState() {
		if (!browser) return;
		const doc = document as Document & { webkitFullscreenElement?: Element | null };
		fullscreenActive = !!(document.fullscreenElement ?? doc.webkitFullscreenElement);
	}

	function toggleZoomMode() {
		dismissZoomHint();
		zoomMode = !zoomMode;
		if (!zoomMode) {
			zoom = 1;
			fitToScreen = true;
			isPanning = false;
		} else {
			fitToScreen = false;
			zoom = Math.max(zoom, 1.2);
		}
	}

	function zoomIn() {
		fitToScreen = false;
		zoom = Math.min(zoom + 0.2, ZOOM_MAX);
	}

	function zoomOut() {
		fitToScreen = false;
		zoom = Math.max(zoom - 0.2, ZOOM_MIN);
	}

	function resetZoom() {
		zoom = 1;
	}

	function wheelShouldIgnore(e: WheelEvent): boolean {
		const t = e.target as HTMLElement | null;
		if (!t?.closest) return false;
		return !!t.closest(
			'.lightbox-carousel, .lightbox-playback-bar, .lightbox-media-actions, .lightbox-controls'
		);
	}

	function onWheel(e: WheelEvent) {
		if (wheelShouldIgnore(e)) return;
		dismissZoomHint();
		e.preventDefault();
		if (zoomMode) {
			fitToScreen = false;
			zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom + (e.deltaY > 0 ? -0.1 : 0.1)));
		} else {
			if (e.deltaY > 0) goNext();
			else goPrev();
		}
	}

	function onMouseDown(e: MouseEvent) {
		if (!zoomMode || !scrollEl) return;
		const t = e.target as HTMLElement;
		if (t.closest('button')) return;
		e.preventDefault();
		isPanning = true;
		panStartX = e.clientX;
		panStartY = e.clientY;
		panStartScrollLeft = scrollEl.scrollLeft;
		panStartScrollTop = scrollEl.scrollTop;
	}

	function onMouseMove(e: MouseEvent) {
		if (!isPanning || !scrollEl) return;
		e.preventDefault();
		scrollEl.scrollLeft = panStartScrollLeft + (panStartX - e.clientX);
		scrollEl.scrollTop = panStartScrollTop + (panStartY - e.clientY);
	}

	function onMouseUp() {
		isPanning = false;
	}

	function wheelAction(node: HTMLDivElement) {
		const handler = (e: WheelEvent) => onWheel(e);
		node.addEventListener('wheel', handler, { passive: false });
		return {
			destroy() {
				node.removeEventListener('wheel', handler);
			}
		};
	}

	function onTouchStart(e: TouchEvent) {
		if (e.touches.length === 1) touchStartX = e.touches[0].clientX;
	}

	function onTouchEnd(e: TouchEvent) {
		if (e.changedTouches.length !== 1 || zoomMode || !items.length) return;
		const deltaX = e.changedTouches[0].clientX - touchStartX;
		if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX) return;
		touchSwipeHandled = true;
		if (deltaX > 0) goPrev();
		else goNext();
		setTimeout(() => {
			touchSwipeHandled = false;
		}, 300);
	}

	function fullscreenHotkeyTargetOk(target: EventTarget | null) {
		const t = target as HTMLElement | null;
		if (!t || !t.closest) return true;
		return !t.closest(
			'button, a, input, textarea, select, audio, video, [contenteditable="true"], [role="textbox"]'
		);
	}

	function handleKey(e: KeyboardEvent) {
		if (!open || !items.length) return;
		dismissZoomHint();
		if (e.key === 'Escape') {
			const doc = document as Document & { webkitFullscreenElement?: Element | null };
			if (document.fullscreenElement ?? doc.webkitFullscreenElement) {
				e.preventDefault();
				void exitFullscreenIfNeeded();
				return;
			}
			void handleClose();
		}
		if (e.key === 'Enter' && !e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
			if (!fullscreenHotkeyTargetOk(e.target)) return;
			e.preventDefault();
			void toggleLightboxFullscreen();
			return;
		}
		if (e.key === 'ArrowRight') goNext();
		if (e.key === 'ArrowLeft') goPrev();
		if ((e.key === 'f' || e.key === 'F') && onToggleFavorite && currentItem) {
			e.preventDefault();
			onToggleFavorite(currentItem);
		}
		if ((e.key === 'd' || e.key === 'D') && onDownload && currentItem && !downloading) {
			e.preventDefault();
			handleDownload(currentItem);
		}
		if (e.key === ' ' && isImage && onToggleSelection && currentItem) {
			e.preventDefault();
			onToggleSelection(currentItem);
		}
		if (e.key === ' ' && isImage && !onToggleSelection && slideshowActive) {
			e.preventDefault();
			slideshowActive = false;
			stopSlideshowTimer();
		}
	}

	function stopSlideshowTimer() {
		if (slideshowTimerId != null) {
			clearTimeout(slideshowTimerId);
			slideshowTimerId = undefined;
		}
	}

	function startSlideshowTimer() {
		stopSlideshowTimer();
		const ms = SLIDESHOW_INTERVALS[slideshowSpeed];
		slideshowTimerId = setTimeout(() => {
			slideshowTimerId = undefined;
			goNext();
		}, ms);
	}

	function toggleSlideshow() {
		slideshowActive = !slideshowActive;
		if (slideshowActive && isImage) startSlideshowTimer();
		else stopSlideshowTimer();
	}

	function onVideoEnded() {
		if (videoLoopMode === 'playlist' && items.length > 1) {
			goNext();
			tick().then(() => {
				videoEl?.play().catch(() => {});
			});
		}
	}

	function onAudioEnded() {
		if (audioPlaylistMode && items.length > 1) {
			goNext();
			tick().then(() => {
				audioEl?.play().catch(() => {});
			});
		}
	}

	function markCarouselLoadFailed(id: string) {
		loadFailedCarousel = new Set([...loadFailedCarousel, id]);
	}

	function markCarouselThumbLoaded(id: string) {
		if (loadedCarouselThumbs.has(id)) return;
		loadedCarouselThumbs = new Set([...loadedCarouselThumbs, id]);
	}

	$effect(() => {
		if (!open || !items.length || !carouselTrackEl) return;
		const idx = index;
		tick().then(() => {
			const active = carouselTrackEl?.querySelector(`[data-carousel-index="${idx}"]`);
			active?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
			const cur = items[idx];
			if (cur?.mediaType === 'video' && videoEl) baseWidth = videoEl.videoWidth || 640;
			else if (imgEl) baseWidth = imgEl.naturalWidth;
		});
	});

	$effect(() => {
		if (!browser) return;
		window.removeEventListener('mousemove', onMouseMove);
		window.removeEventListener('mouseup', onMouseUp);
		if (open && isPanning) {
			window.addEventListener('mousemove', onMouseMove);
			window.addEventListener('mouseup', onMouseUp);
		}
		return () => {
			window.removeEventListener('mousemove', onMouseMove);
			window.removeEventListener('mouseup', onMouseUp);
		};
	});

	$effect(() => {
		if (open && currentItem && currentItem.mediaType !== 'video' && currentItem.mediaType !== 'audio' && browser && !sessionStorage.getItem('workflowui_lightbox_zoom_hint_seen')) {
			zoomHintVisible = true;
			zoomHintTimeoutId = setTimeout(() => dismissZoomHint(), 5000);
		}
		return () => {
			if (zoomHintTimeoutId != null) clearTimeout(zoomHintTimeoutId);
		};
	});

	onMount(() => {
		if (!browser) return;
		window.addEventListener('keydown', handleKey);
		document.addEventListener('fullscreenchange', syncFullscreenState);
		document.addEventListener('webkitfullscreenchange', syncFullscreenState as EventListener);
		syncFullscreenState();
	});

	onDestroy(() => {
		if (!browser) return;
		window.removeEventListener('keydown', handleKey);
		document.removeEventListener('fullscreenchange', syncFullscreenState);
		document.removeEventListener('webkitfullscreenchange', syncFullscreenState as EventListener);
		stopSlideshowTimer();
		void exitFullscreenIfNeeded();
	});

	$effect(() => {
		if (!open) {
			loadFailed = false;
			loadFailedCarousel = new Set();
			loadedCarouselThumbs = new Set();
		}
	});

	$effect(() => {
		if (!open || !slideshowActive || !items.length) {
			stopSlideshowTimer();
			return;
		}
		const cur = items[index];
		const curIsImage = cur?.mediaType === 'image' || (cur?.mediaType == null && cur);
		if (curIsImage) startSlideshowTimer();
		else stopSlideshowTimer();
		return () => stopSlideshowTimer();
	});

	// Fit: scale video to use viewport (fill width, constrain height, or vice versa so it fits). Actual: native pixel size (may overflow on high-res).
	const videoStyle = $derived.by(() => {
		if (videoFitMode === 'actual' && baseWidth > 0) {
			return `width: ${baseWidth * zoom}px; height: auto;`;
		}
		// Fit: use full available space (scale up or down to fit viewport)
		return fitToScreen
			? 'width: 100%; max-width: 100%; height: auto; max-height: 100%; object-fit: contain;'
			: `width: ${baseWidth * zoom}px; height: auto;`;
	});

	const mediaStyle = $derived.by(() => {
		if (zoomMode) {
			return `width: ${baseWidth * zoom}px; height: auto;`;
		}
		if (imageFitMode === 'fit') {
			// Match video “fit” path so the image scales to the scroll viewport (flex min-size is fixed in lightbox.css).
			return 'width: 100%; max-width: 100%; height: auto; max-height: 100%; object-fit: contain;';
		}
		if (baseWidth > 0) {
			return `width: ${baseWidth}px; height: auto;`;
		}
		return 'max-width: 100%; max-height: 100%; width: auto; height: auto;';
	});

	const showDeleted = $derived(currentItem?.remote_deleted && loadFailed);
</script>

{#if open}
	<div class="lightbox" bind:this={lightboxRootEl} role="dialog" aria-modal="true" aria-label={ariaTitle} use:wheelAction>
		<div
			class="lightbox-backdrop"
			role="button"
			tabindex="-1"
			aria-label="Close viewer"
			title="Click outside the media to close · Esc"
			onclick={handleClose}
			onkeydown={(e) => e.key === 'Enter' && handleClose()}
		></div>
		<div class="lightbox-controls" role="group" aria-label="Lightbox controls">
			<button
				type="button"
				class="lightbox-zoom-mode"
				class:active={zoomMode}
				onclick={(e) => {
					e.stopPropagation();
					toggleZoomMode();
				}}
				title={zoomMode ? 'Exit zoom mode (wheel will change image)' : 'Enter zoom mode (wheel zooms, drag to pan)'}
				aria-label={zoomMode ? 'Exit zoom mode' : 'Enter zoom mode'}
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="11" cy="11" r="8" />
					<line x1="21" y1="21" x2="16.65" y2="16.65" />
					<line x1="11" y1="8" x2="11" y2="14" />
					<line x1="8" y1="11" x2="14" y2="11" />
				</svg>
			</button>
			<button type="button" onclick={zoomOut} disabled={!zoomMode}>−</button>
			<button type="button" onclick={resetZoom}>{Math.round(zoom * 100)}%</button>
			<button type="button" onclick={zoomIn} disabled={!zoomMode}>+</button>
			<button type="button" class="close" onclick={handleClose} title="Close (Esc)" aria-label="Close viewer">
				✕ {#if showCloseLabel}Close{/if}
			</button>
			{#if currentItem && ((isImage && onToggleSelection && isSelected) || (onToggleFavorite && isFavorite) || onDownload)}
				<div class="lightbox-controls-shortcuts" role="note" aria-label="Keyboard shortcuts">
					{#if isImage && onToggleSelection && isSelected}
						<span class="lightbox-shortcut-pill"><kbd>Space</kbd> select</span>
					{/if}
					{#if onToggleFavorite && isFavorite}
						<span class="lightbox-shortcut-pill"><kbd>F</kbd> favorite</span>
					{/if}
					{#if onDownload}
						<span class="lightbox-shortcut-pill"><kbd>D</kbd> download</span>
					{/if}
				</div>
			{/if}
		</div>

		<div
			class="lightbox-scroll"
			class:zoom-mode={zoomMode}
			class:panning={isPanning}
			bind:this={scrollEl}
			role="presentation"
			ondblclick={(e) => {
				const t = e.target as HTMLElement;
				if (t.tagName === 'IMG') {
					e.preventDefault();
					toggleZoomMode();
				}
			}}
			onmousedown={onMouseDown}
			ontouchstart={onTouchStart}
			ontouchend={onTouchEnd}
			onclick={(e) => {
				if (touchSwipeHandled) {
					e.preventDefault();
					e.stopPropagation();
					return;
				}
				const t = e.target as HTMLElement;
				if (t.tagName === 'IMG' || t.tagName === 'VIDEO' || t.tagName === 'AUDIO') dismissZoomHint();
				if (t.tagName !== 'IMG' && t.tagName !== 'VIDEO' && t.tagName !== 'AUDIO' && !t.closest('button') && !t.closest('audio')) handleClose();
			}}
			onkeydown={(e) => {
				if (e.key !== 'Escape') return;
				const doc = document as Document & { webkitFullscreenElement?: Element | null };
				if (document.fullscreenElement ?? doc.webkitFullscreenElement) {
					e.preventDefault();
					void exitFullscreenIfNeeded();
					return;
				}
				void handleClose();
			}}
		>
			{#if open && zoomHintVisible && !isVideo && !isAudio}
				<p class="lightbox-zoom-hint visible" role="status" aria-live="polite">Double-click to zoom · drag to pan</p>
			{/if}
			<div class="lightbox-inner">
				<button
					type="button"
					class="lightbox-nav lightbox-prev"
					onclick={(e) => {
						e.stopPropagation();
						goPrev();
					}}
					ondblclick={(e) => {
						e.preventDefault();
						e.stopPropagation();
					}}
					aria-label="Previous"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M19 12H5M12 19l-7-7 7-7" />
					</svg>
				</button>
				<div class="lightbox-media-center">
					<button
						type="button"
						class="lightbox-dismiss-sash"
						aria-label="Close viewer"
						title="Close · Esc"
						onclick={(e) => {
							e.stopPropagation();
							void handleClose();
						}}
					></button>
					<div class="lightbox-media-slot">
						{#if showDeleted}
							<div class="lightbox-deleted-placeholder">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M8 6l1 14h6l1-14"/></svg>
								<span>Deleted</span>
							</div>
						{:else if isVideo && currentItem}
							<video
								bind:this={videoEl}
								class="lightbox-media"
								src={currentItem.url}
								controls
								autoplay
								playsinline
								loop={videoLoopMode === 'single'}
								style={videoStyle}
								onended={onVideoEnded}
								onerror={() => {
									loadFailed = true;
								}}
							><track kind="captions" /></video>
						{:else if isAudio && currentItem}
							<div class="lightbox-audio-wrap">
								<audio
									bind:this={audioEl}
									class="lightbox-media lightbox-audio"
									src={currentItem.url}
									controls
									autoplay
									onended={onAudioEnded}
									onerror={() => {
										loadFailed = true;
									}}
								></audio>
							</div>
						{:else if currentItem}
							<img
								bind:this={imgEl}
								src={currentItem.url}
								alt=""
								draggable="false"
								style={mediaStyle}
								onerror={() => {
									loadFailed = true;
								}}
							/>
						{/if}
						{#if currentItem && isSendingToVault?.(currentItem)}
							<div class="lightbox-transfer-overlay" aria-hidden="true">
								<span class="lightbox-transfer-label">Sending to GenVault…</span>
								<span class="lightbox-transfer-bar"><span class="lightbox-transfer-bar-fill"></span></span>
							</div>
						{/if}
					</div>
					<button
						type="button"
						class="lightbox-dismiss-sash"
						aria-label="Close viewer"
						title="Close · Esc"
						onclick={(e) => {
							e.stopPropagation();
							void handleClose();
						}}
					></button>
				</div>
				<button
					type="button"
					class="lightbox-nav lightbox-next"
					onclick={(e) => {
						e.stopPropagation();
						goNext();
					}}
					ondblclick={(e) => {
						e.preventDefault();
						e.stopPropagation();
					}}
					aria-label="Next"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M5 12h14M12 5l7 7-7 7" />
					</svg>
				</button>
			</div>
		</div>

		{#if currentItem}
			{@const img = currentItem}
			{@const hasSeed = img.seed !== undefined && img.seed !== null && String(img.seed).trim() !== ''}
			{@const hasTime = img.executionTimeSec != null}
			{@const hasFilename = !!img.filename}
			{@const showMeta = !!onMetadata}
			{@const showFav = !!onToggleFavorite && !!isFavorite}
			{@const showSel = !!onToggleSelection && !!isSelected}
			{@const hasRemote = img.hasRemote ?? !img.remote_deleted}
			{@const hasLocal = img.hasLocal ?? true}
			{@const showSend = !!onSendToApp && !img.remote_deleted}
			{@const showSendVault = !!onSendToVault && !img.remote_deleted}
			{@const inVault = !!isInVault?.(img)}
			{@const sendingToVault = !!isSendingToVault?.(img)}
			{@const showDeleteLocal = !!onDeleteLocal && hasLocal}
			{@const showDeleteRemote = !!onDeleteRemote && hasRemote}
			{@const showDeleteBoth = !!onDeleteBoth && hasLocal && hasRemote}
			<div class="lightbox-media-actions" role="toolbar" aria-label="Media actions">
				<div class="lightbox-media-actions-left">
					{#if showMeta}
						<button
							type="button"
							class="lightbox-media-btn"
							title="View generation metadata"
							aria-label="View generation metadata"
							onclick={(e) => {
								e.stopPropagation();
								handleClose();
								onMetadata?.(img);
							}}
						>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<circle cx="12" cy="12" r="10" />
								<path d="M12 16v-4" />
								<path d="M12 8h.01" />
							</svg>
						</button>
					{/if}
					{#if hasSeed || hasTime}
						<span class="lightbox-media-seed" title={[hasSeed ? 'Seed value' : '', hasTime ? 'Generation time' : ''].filter(Boolean).join(' · ') || undefined}>
							{#if hasSeed}
								<span class="seed-value">{img.seed}</span>
							{/if}
							{#if hasTime}
								{#if hasSeed}
									<span class="lightbox-media-sep" aria-hidden="true"> · </span>
								{/if}
								<span class="lightbox-media-time">{Math.round(Number(img.executionTimeSec))} sec</span>
							{/if}
						</span>
					{/if}
					{#if hasFilename}
						<div class="lightbox-media-filename" title={img.filename}>
							{img.filename}
						</div>
					{/if}
				</div>
				<div class="lightbox-media-actions-right">
					{#if showFav}
						<button
							type="button"
							class="lightbox-media-btn lightbox-media-favorite"
							class:is-favorite={isFavorite?.(img)}
							title={isFavorite?.(img) ? 'Remove from favorites (F)' : 'Add to favorites (F)'}
							aria-label={isFavorite?.(img) ? 'Remove from favorites (F)' : 'Add to favorites (F)'}
							onclick={(e) => {
								e.stopPropagation();
								onToggleFavorite?.(img);
							}}
						>
							<span class="lightbox-fav-outline" aria-hidden="true">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round">
									<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
								</svg>
							</span>
							<span class="lightbox-fav-fill" aria-hidden="true">
								<svg viewBox="0 0 24 24" fill="currentColor">
									<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
								</svg>
							</span>
						</button>
					{/if}
					{#if showSel}
						<button
							type="button"
							class="lightbox-media-btn lightbox-media-select"
							class:active={isSelected?.(img)}
							title={isSelected?.(img) ? 'Remove from selection (Space)' : 'Add to selection (Space)'}
							aria-label={isSelected?.(img) ? 'Remove from selection (Space)' : 'Add to selection (Space)'}
							onclick={(e) => {
								e.stopPropagation();
								onToggleSelection?.(img);
							}}
						>
							{#if isSelected?.(img)}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>
							{:else}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
							{/if}
						</button>
					{/if}
					{#if showDeleteLocal || showDeleteRemote || showDeleteBoth}
						<div class="lightbox-media-delete-group">
							{#if showDeleteLocal}
								<button
									type="button"
									class="lightbox-media-btn lightbox-media-delete lightbox-media-delete-local"
									title="Delete local copy"
									aria-label="Delete local copy"
									onclick={(e) => {
										e.stopPropagation();
										onDeleteLocal?.(img);
									}}
								>
									<span class="lightbox-media-delete-icon" aria-hidden="true">
										<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
											<path d="M3 6h18" />
											<path d="M8 6V4h8v2" />
											<path d="M10 11v6" />
											<path d="M14 11v6" />
											<path d="M6 6l1 14h10l1-14" />
										</svg>
									</span>
								</button>
							{/if}
							{#if showDeleteRemote}
								<button
									type="button"
									class="lightbox-media-btn lightbox-media-delete lightbox-media-delete-remote"
									title="Delete remote copy"
									aria-label="Delete remote copy"
									onclick={(e) => {
										e.stopPropagation();
										onDeleteRemote?.(img);
									}}
								>
									<span class="lightbox-media-delete-icon" aria-hidden="true">
										<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
											<path d="M3 6h18" />
											<path d="M8 6V4h8v2" />
											<path d="M10 11v6" />
											<path d="M14 11v6" />
											<path d="M6 6l1 14h10l1-14" />
										</svg>
									</span>
								</button>
							{/if}
							{#if showDeleteBoth}
								<button
									type="button"
									class="lightbox-media-btn lightbox-media-delete lightbox-media-delete-both"
									title="Delete local and remote copies"
									aria-label="Delete local and remote copies"
									onclick={(e) => {
										e.stopPropagation();
										onDeleteBoth?.(img);
									}}
								>
									<span class="lightbox-media-delete-icon" aria-hidden="true">
										<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
											<path d="M3 6h18" />
											<path d="M8 6V4h8v2" />
											<path d="M10 11v6" />
											<path d="M14 11v6" />
											<path d="M6 6l1 14h10l1-14" />
										</svg>
									</span>
								</button>
							{/if}
						</div>
					{/if}
					{#if onDownload}
						<button
							type="button"
							class="lightbox-media-btn"
							disabled={downloading}
							title={downloading ? 'Downloading…' : 'Download file (D)'}
							aria-label={downloading ? 'Downloading…' : 'Download file (D)'}
							onclick={(e) => {
								e.stopPropagation();
								handleDownload(img);
							}}
						>
							{#if downloading}
								<span class="lightbox-download-spinner" aria-hidden="true"></span>
							{:else}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
									<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
									<path d="M7 10l5 5 5-5" />
									<path d="M12 15V3" />
								</svg>
							{/if}
						</button>
					{/if}
					{#if showSend}
						<button
							type="button"
							class="lightbox-media-btn"
							title="Send this output to app"
							aria-label="Send this output to app"
							onclick={(e) => {
								e.stopPropagation();
								handleClose();
								onSendToApp?.(img);
							}}
						>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
								<path d="M5 12h14M12 5l7 7-7 7" />
							</svg>
						</button>
					{/if}
					{#if showSendVault}
						<button
							type="button"
							class="lightbox-media-btn"
							class:lightbox-media-btn-active={inVault}
							disabled={sendingToVault}
							title="Save to GenVault"
							aria-label="Save to GenVault"
							onclick={(e) => {
								e.stopPropagation();
								onSendToVault?.(img);
							}}
						>
							{#if sendingToVault}
								<span class="lightbox-send-spinner" aria-hidden="true"></span>
							{:else}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
									<rect x="3" y="3" width="18" height="18" rx="2" />
									<path d="M8 12h8" />
									<path d="M12 8v8" />
								</svg>
							{/if}
						</button>
					{/if}
					<span class="lightbox-media-toolbar-sep" aria-hidden="true"></span>
					<button
						type="button"
						class="lightbox-media-btn lightbox-media-close"
						title="Close viewer (Esc)"
						aria-label="Close viewer"
						onclick={(e) => {
							e.stopPropagation();
							void handleClose();
						}}
					>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M18 6L6 18M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>
		{/if}

		{#if isVideo || isAudio || isImage}
		<div class="lightbox-playback-bar" role="group" aria-label="Playback and size options">
			{#if isVideo}
				<span class="lightbox-controls-label">Size:</span>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={videoFitMode === 'fit'}
					onclick={() => persistVideoFit('fit')}
					title="Scale video to fit within window (use full viewport)"
					aria-label="Fit: scale to fit within window"
					aria-pressed={videoFitMode === 'fit'}
				>Fit</button>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={videoFitMode === 'actual'}
					onclick={() => persistVideoFit('actual')}
					title="Show video at native resolution (may be larger than window)"
					aria-label="Actual: native resolution"
					aria-pressed={videoFitMode === 'actual'}
				>Actual</button>
				<span class="lightbox-controls-sep" aria-hidden="true">|</span>
				<span class="lightbox-controls-label">Playback:</span>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={videoLoopMode === 'single'}
					onclick={() => persistVideoLoop('single')}
					title="Loop single video"
					aria-pressed={videoLoopMode === 'single'}
				>Single</button>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={videoLoopMode === 'playlist'}
					onclick={() => persistVideoLoop('playlist')}
					title="Play all videos in sequence, then repeat"
					aria-pressed={videoLoopMode === 'playlist'}
				>Playlist</button>
			{:else if isAudio}
				<span class="lightbox-controls-label">Playback:</span>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={!audioPlaylistMode}
					onclick={() => persistAudioPlaylist(false)}
					title="Play single"
					aria-pressed={!audioPlaylistMode}
				>Single</button>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={audioPlaylistMode}
					onclick={() => persistAudioPlaylist(true)}
					title="Play all in sequence, then repeat"
					aria-pressed={audioPlaylistMode}
				>Playlist</button>
			{:else if isImage}
				<span class="lightbox-controls-label">Size:</span>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={imageFitMode === 'fit'}
					onclick={() => persistImageFit('fit')}
					title="Fit image within the viewer (use available space)"
					aria-label="Fit: scale to fit within viewer"
					aria-pressed={imageFitMode === 'fit'}
				>Fit</button>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={imageFitMode === 'actual'}
					onclick={() => persistImageFit('actual')}
					title="Original pixel size (may be larger than the window; scroll to see all)"
					aria-label="Actual: original size"
					aria-pressed={imageFitMode === 'actual'}
				>Actual</button>
				<button
					type="button"
					class="lightbox-controls-segmented lightbox-fullscreen-btn"
					class:active={fullscreenActive}
					onclick={(ev) => {
						ev.stopPropagation();
						void toggleLightboxFullscreen();
					}}
					title={fullscreenActive ? 'Exit full screen (Enter)' : 'Full screen viewer (Enter)'}
					aria-label={fullscreenActive ? 'Exit full screen, shortcut Enter' : 'Enter full screen, shortcut Enter'}
					aria-pressed={fullscreenActive}
				>
					{#if fullscreenActive}
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
						</svg>
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
						</svg>
					{/if}
				</button>
				<span class="lightbox-controls-sep" aria-hidden="true">|</span>
				<span class="lightbox-controls-label">Slideshow:</span>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={!slideshowActive}
					onclick={() => {
						slideshowActive = false;
						stopSlideshowTimer();
					}}
					title="Slideshow off"
					aria-pressed={!slideshowActive}
				>Off</button>
				<button
					type="button"
					class="lightbox-controls-segmented"
					class:active={slideshowActive}
					onclick={toggleSlideshow}
					title="Slideshow on"
					aria-pressed={slideshowActive}
				>On</button>
				{#if slideshowActive}
					<button
						type="button"
						class="lightbox-controls-segmented"
						class:active={slideshowSpeed === 'slow'}
						onclick={() => {
							persistSlideshowSpeed('slow');
							if (slideshowActive) startSlideshowTimer();
						}}
						title="5 s per image"
						aria-pressed={slideshowSpeed === 'slow'}
					>Slow</button>
					<button
						type="button"
						class="lightbox-controls-segmented"
						class:active={slideshowSpeed === 'medium'}
						onclick={() => {
							persistSlideshowSpeed('medium');
							if (slideshowActive) startSlideshowTimer();
						}}
						title="3 s per image"
						aria-pressed={slideshowSpeed === 'medium'}
					>Med</button>
					<button
						type="button"
						class="lightbox-controls-segmented"
						class:active={slideshowSpeed === 'fast'}
						onclick={() => {
							persistSlideshowSpeed('fast');
							if (slideshowActive) startSlideshowTimer();
						}}
						title="1.5 s per image"
						aria-pressed={slideshowSpeed === 'fast'}
					>Fast</button>
				{/if}
			{/if}
		</div>
		{/if}

		<div class="lightbox-carousel" role="tablist" aria-label="Media strip" tabindex="0">
			<div class="lightbox-carousel-track" bind:this={carouselTrackEl}>
				{#each items as item, i (item.id)}
					{@const carouselShowDeleted = item.remote_deleted && loadFailedCarousel.has(item.id)}
					<button
						type="button"
						class="lightbox-carousel-thumb"
						class:active={i === index}
						class:deleted={carouselShowDeleted}
						data-carousel-index={i}
						onclick={() => goTo(i)}
						aria-label={carouselShowDeleted ? `Deleted ${i + 1}` : item.mediaType === 'video' ? `Video ${i + 1}` : item.mediaType === 'audio' ? `Audio ${i + 1}` : `Image ${i + 1}`}
						aria-selected={i === index}
						role="tab"
					>
						{#if carouselShowDeleted}
							<span class="lightbox-carousel-deleted" aria-hidden="true">Deleted</span>
						{:else if item.mediaType === 'video'}
							<span class="lightbox-carousel-video-thumb" aria-hidden="true">
								{#if !loadedCarouselThumbs.has(item.id)}
									<span class="lightbox-carousel-thumb-loading" aria-hidden="true"></span>
								{/if}
								<img
									src={item.thumbnailUrl ?? item.url}
									alt=""
									draggable="false"
									onload={() => markCarouselThumbLoaded(item.id)}
									onerror={() => {
										markCarouselThumbLoaded(item.id);
										markCarouselLoadFailed(item.id);
									}}
								/>
							</span>
							<span class="lightbox-carousel-play" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></span>
						{:else if item.mediaType === 'audio'}
							<span class="lightbox-carousel-audio" aria-hidden="true">
								<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v9.28c-.47-.17-.97-.28-1.5-.28C8.01 12 6 14.01 6 16.5S8.01 21 10.5 21c2.31 0 4.2-1.75 4.45-4H15V6h4V3h-7z"/></svg>
								<span>Audio</span>
							</span>
						{:else}
							<img src={item.url} alt="" draggable="false" onerror={() => markCarouselLoadFailed(item.id)} />
						{/if}
					</button>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.lightbox-media-delete-group {
		display: inline-flex;
		gap: 0.15rem;
	}
	.lightbox-media-delete {
		padding: 0.25rem;
	}
	.lightbox-media-delete-icon svg {
		width: 16px;
		height: 16px;
	}
	.lightbox-media-delete-local {
		color: var(--accent);
	}
	.lightbox-media-delete-remote {
		color: var(--warning, #92400e);
	}
	.lightbox-media-delete-both {
		color: var(--error, #b91c1c);
	}
	.lightbox-media-btn-active {
		border-color: color-mix(in srgb, var(--accent) 70%, var(--border));
		background: color-mix(in srgb, var(--accent) 28%, rgba(0, 0, 0, 0.55));
		color: var(--accent);
	}
	.lightbox-send-spinner {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: rgba(255, 255, 255, 0.95);
		animation: workflowui-lightbox-spin 0.8s linear infinite;
	}
	.lightbox-transfer-overlay {
		position: absolute;
		inset: 0;
		z-index: 8;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		padding: 1rem;
		background: rgba(10, 12, 20, 0.5);
		backdrop-filter: blur(5px);
		pointer-events: none;
	}
	.lightbox-transfer-label {
		font-size: 0.9rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.96);
		text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
	}
	.lightbox-transfer-bar {
		width: min(68%, 320px);
		height: 5px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(255, 255, 255, 0.22);
		border: 1px solid rgba(255, 255, 255, 0.2);
	}
	.lightbox-transfer-bar-fill {
		display: block;
		height: 100%;
		width: 42%;
		border-radius: 999px;
		background: linear-gradient(
			90deg,
			rgba(255, 255, 255, 0.25) 0%,
			color-mix(in srgb, var(--accent) 80%, #9fb4ff) 38%,
			color-mix(in srgb, var(--accent) 65%, #dbe5ff) 62%,
			rgba(255, 255, 255, 0.2) 100%
		);
		animation: lightbox-transfer-slide 1.15s ease-in-out infinite;
	}
	@keyframes lightbox-transfer-slide {
		0% { transform: translateX(-110%); }
		100% { transform: translateX(250%); }
	}
	.lightbox-media-filename {
		margin-top: 0.15rem;
		font-size: 0.75rem;
		color: var(--lightbox-muted, #9ca3af);
		max-width: 100%;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.lightbox-controls-shortcuts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
		margin-left: 0.35rem;
	}
	.lightbox-shortcut-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.72rem;
		color: var(--lightbox-muted, #9ca3af);
		background: rgba(17, 24, 39, 0.55);
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: 999px;
		padding: 0.12rem 0.5rem;
	}
	.lightbox-shortcut-pill kbd {
		font: inherit;
		font-weight: 600;
		color: #f3f4f6;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 0.3rem;
		padding: 0 0.3rem;
		line-height: 1.35;
	}

	@media (max-width: 639px) {
		/* Mobile layout is already dense; remove the keyboard shortcut "legend" to free space. */
		.lightbox-controls-shortcuts {
			display: none;
		}

		/* Make the close ("X") button larger so it stays tappable even with fewer controls. */
		.lightbox-controls .close {
			width: 34px;
			height: 34px;
			padding: 0;
			margin-left: 8px;
			border-radius: 8px;
			border-left: none;
			border: 1px solid rgba(255, 255, 255, 0.22);
			background: rgba(0, 0, 0, 0.35);
			display: inline-flex;
			flex-shrink: 0;
			align-items: center;
			justify-content: center;
			font-size: 1.1rem;
			line-height: 1;
		}

		/* Keep the icon visually centered if the "Close" label is shown for some call sites. */
		.lightbox-controls .close :global(svg),
		.lightbox-controls .close {
			white-space: nowrap;
		}
	}

	.lightbox-carousel-video-thumb {
		position: relative;
		display: block;
		width: 100%;
		height: 100%;
	}
	.lightbox-carousel-video-thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.lightbox-carousel-thumb-loading {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.lightbox-carousel-thumb-loading::before {
		content: '';
		width: 18px;
		height: 18px;
		border-radius: 999px;
		border: 2px solid rgba(255, 255, 255, 0.25);
		border-top-color: rgba(255, 255, 255, 0.85);
		animation: workflowui-lightbox-spin 0.8s linear infinite;
	}
	@keyframes workflowui-lightbox-spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
