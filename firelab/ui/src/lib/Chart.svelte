<script>
  // A plain SVG line chart. No dependency, no axes clutter: shape over precision.
  let { series = [], height = 74, label = '', unit = '' } = $props();

  const WIDTH = 300;

  // A series of nothing but gaps would break the scaling below, so drop it.
  const drawn = $derived(series.filter((s) => s.points.some((p) => p !== null)));

  // Rescale to whatever is on screen; zero is always included so growth reads honestly.
  const bounds = $derived.by(() => {
    const values = drawn.flatMap((s) => s.points).filter((p) => p !== null);
    if (!values.length) return { min: 0, max: 1 };
    const min = Math.min(...values, 0);
    const max = Math.max(...values);
    return { min, max: max - min < 1e-6 ? min + 1 : max };
  });

  function path(points) {
    const { min, max } = bounds;
    const step = points.length > 1 ? WIDTH / (points.length - 1) : WIDTH;
    let d = '';
    let pen = 'M';
    points.forEach((value, index) => {
      if (value === null) {
        pen = 'M'; // a missing sample lifts the pen, so dropouts show as a break
        return;
      }
      const y = height - ((value - min) / (max - min)) * (height - 6) - 3;
      d += `${pen}${(index * step).toFixed(1)} ${y.toFixed(1)} `;
      pen = 'L';
    });
    return d.trim();
  }

  function fmt(value) {
    if (value === null || value === undefined) return '—';
    return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
  }
</script>

<figure>
  <figcaption>
    <span>{label}</span>
    <span class="keys">
      {#each drawn as s (s.name)}
        <span class="key"><i style="background:{s.color}"></i>{s.name}</span>
      {/each}
    </span>
  </figcaption>
  {#if drawn.length}
    <svg viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="none" role="img" aria-label={label}>
      {#each drawn as s (s.name)}
        <path d={path(s.points)} stroke={s.color} fill="none" stroke-width="1.6" />
      {/each}
    </svg>
    <span class="scale mono">{fmt(bounds.max)}{unit} · {fmt(bounds.min)}{unit}</span>
  {:else}
    <p class="muted empty">No samples yet.</p>
  {/if}
</figure>

<style>
  figure { margin: 0 0 12px; }
  figcaption {
    display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
    font-size: 11px; color: var(--muted); margin-bottom: 3px;
  }
  .keys { display: flex; gap: 8px; }
  .key { display: inline-flex; align-items: center; gap: 4px; }
  .key i { width: 9px; height: 2px; border-radius: 1px; }
  svg {
    display: block; width: 100%; height: 74px;
    background: #0d1420; border: 1px solid var(--line); border-radius: 8px;
  }
  .scale { display: block; text-align: right; font-size: 10px; color: var(--muted); margin-top: 2px; }
  .empty { font-size: 12px; margin: 4px 0 0; }
</style>
