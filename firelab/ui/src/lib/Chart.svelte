<!-- Reusable history chart for the selected room; data comes from the API snapshot. -->
<script>
  // A plain SVG line chart with a labelled y axis, a time axis, and optional
  // horizontal marks (the alarm thresholds on the P(fire) chart). No dependency.
  //
  // `series`  [{name, color, points}] with one point per history sample, null for a gap
  // `unit`    appended to the y labels
  // `max`     fixes the top of the y axis (P(fire) is always drawn 0..1)
  // `marks`   [{value, label, color}] horizontal reference lines
  // `sampleSeconds` simulated seconds between history samples (history.py: 5)
  let {
    series = [],
    height = 120,
    label = '',
    unit = '',
    max = null,
    marks = [],
    sampleSeconds = 5
  } = $props();

  const WIDTH = 300;
  const LEFT = 34; // room for the y labels
  const RIGHT = 6;
  const TOP = 5;
  const BOTTOM = 14; // room for the time labels
  const plotW = WIDTH - LEFT - RIGHT;
  const plotH = $derived(height - TOP - BOTTOM);

  // A series of nothing but gaps would break the scaling below, so drop it.
  const drawn = $derived(series.filter((s) => s.points.some((p) => p !== null)));
  const count = $derived(Math.max(...drawn.map((s) => s.points.length), 0));

  // Rescale to whatever is on screen; zero is always included so growth reads honestly,
  // and every mark is kept in view so a threshold never sits above the chart.
  const bounds = $derived.by(() => {
    const values = drawn.flatMap((s) => s.points).filter((p) => p !== null);
    const min = Math.min(...values, 0);
    let hi = Math.max(...values, ...marks.map((m) => m.value), max ?? -Infinity);
    if (!Number.isFinite(hi) || hi - min < 1e-6) hi = min + 1;
    return { min, max: hi };
  });

  // A round step (1, 2 or 5 times a power of ten) that gives three or four gridlines.
  function niceStep(range) {
    const raw = range / 3;
    const power = 10 ** Math.floor(Math.log10(raw));
    const f = raw / power;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * power;
  }

  const yTicks = $derived.by(() => {
    const { min, max } = bounds;
    const step = niceStep(max - min);
    const ticks = [];
    for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(v);
    return ticks;
  });

  // Time runs left to right and ends at "now"; ticks every five minutes when the
  // window is long enough to need them, every minute otherwise.
  const xTicks = $derived.by(() => {
    if (count < 2) return [];
    const span = (count - 1) * sampleSeconds;
    const every = span >= 600 ? 300 : 60;
    const ticks = [];
    for (let ago = 0; ago <= span; ago += every) {
      const index = count - 1 - ago / sampleSeconds;
      ticks.push({ x: x(index), text: ago === 0 ? 'now' : `-${ago / 60} min` });
    }
    return ticks;
  });

  const x = (index) => LEFT + (count > 1 ? (index / (count - 1)) * plotW : 0);
  const y = (value) => TOP + plotH - ((value - bounds.min) / (bounds.max - bounds.min)) * plotH;

  function path(points) {
    let d = '';
    let pen = 'M';
    points.forEach((value, index) => {
      if (value === null) {
        pen = 'M'; // a missing sample lifts the pen, so dropouts show as a break
        return;
      }
      d += `${pen}${x(index).toFixed(1)} ${y(value).toFixed(1)} `;
      pen = 'L';
    });
    return d.trim();
  }

  function fmt(value) {
    if (value === null || value === undefined) return '—';
    if (Math.abs(value) >= 100) return value.toFixed(0);
    if (Math.abs(value) >= 10) return value.toFixed(1);
    return value.toFixed(2);
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
    <svg viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="xMinYMin meet" role="img" aria-label={label}>
      {#each yTicks as tick (tick)}
        <line class="grid" x1={LEFT} x2={WIDTH - RIGHT} y1={y(tick)} y2={y(tick)} />
        <text class="axis" x={LEFT - 3} y={y(tick) + 2.5} text-anchor="end">{fmt(tick)}{unit}</text>
      {/each}
      {#each xTicks as tick (tick.text)}
        <line class="tick" x1={tick.x} x2={tick.x} y1={TOP + plotH} y2={TOP + plotH + 3} />
        <text class="axis" x={tick.x} y={height - 3} text-anchor={tick.text === 'now' ? 'end' : 'middle'}>{tick.text}</text>
      {/each}
      <line class="frame" x1={LEFT} x2={LEFT} y1={TOP} y2={TOP + plotH} />
      <line class="frame" x1={LEFT} x2={WIDTH - RIGHT} y1={TOP + plotH} y2={TOP + plotH} />
      {#each marks as mark (mark.label)}
        <line class="mark" x1={LEFT} x2={WIDTH - RIGHT} y1={y(mark.value)} y2={y(mark.value)} style="stroke:{mark.color}" />
        <text class="axis" x={WIDTH - RIGHT - 2} y={y(mark.value) - 2} text-anchor="end" style="fill:{mark.color}">{mark.label} {fmt(mark.value)}</text>
      {/each}
      {#each drawn as s (s.name)}
        <path d={path(s.points)} stroke={s.color} fill="none" stroke-width="1.4" />
      {/each}
    </svg>
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
    display: block; width: 100%; height: auto;
    background: #0d1420; border: 1px solid var(--line); border-radius: 8px;
  }
  .grid { stroke: var(--line); stroke-width: 0.5; }
  .frame { stroke: var(--muted); stroke-width: 0.6; }
  .tick { stroke: var(--muted); stroke-width: 0.6; }
  .mark { stroke-width: 0.7; stroke-dasharray: 3 2; opacity: 0.8; }
  .axis { fill: var(--muted); font-size: 7px; font-family: ui-monospace, Menlo, Consolas, monospace; }
  .empty { font-size: 12px; margin: 4px 0 0; }
</style>
