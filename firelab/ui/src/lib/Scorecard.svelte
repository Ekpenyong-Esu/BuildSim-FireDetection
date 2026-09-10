<script>
  import { store } from './store.svelte.js';

  const score = $derived(store.snapshot?.score);

  function seconds(value) {
    if (value === null || value === undefined) return '—';
    return value >= 60 ? `${Math.floor(value / 60)}m ${Math.round(value % 60)}s` : `${Math.round(value)}s`;
  }

  // The snapshot identifies rooms by key; people recognise them by name.
  function nameOf(key) {
    return store.rooms.find((r) => r.key === key)?.name ?? key;
  }
</script>

<section class="panel">
  <h2>Scorecard</h2>
  <p class="hint">
    Every source carries its own ground-truth label, so the run grades itself: caught, missed, or
    fooled.
  </p>

  <div class="cards">
    <div class="card good">
      <strong>{score?.detections ?? 0}</strong>
      <span>caught</span>
    </div>
    <div class="card bad" class:lit={score?.misses}>
      <strong>{score?.misses ?? 0}</strong>
      <span>missed</span>
    </div>
    <div class="card warn" class:lit={score?.false_alarms}>
      <strong>{score?.false_alarms ?? 0}</strong>
      <span>false alarms</span>
    </div>
  </div>

  <dl class="latency">
    <div><dt>Mean time to confirm</dt><dd class="mono">{seconds(score?.mean_latency)}</dd></div>
    <div><dt>Slowest</dt><dd class="mono">{seconds(score?.worst_latency)}</dd></div>
  </dl>

  <p class="hint">
    Detection only matters through the clearance time it buys. RSET is measured from ignition to
    the last person out.
  </p>
  <dl class="latency">
    <div><dt>Ignition to alarm</dt><dd class="mono">{seconds(score?.alarm_delay)}</dd></div>
    <div>
      <dt>Alarm to building clear</dt>
      <dd class="mono">{score?.clearing ? 'evacuating…' : seconds(score?.rset_from_alarm)}</dd>
    </div>
    <div><dt>RSET, total</dt><dd class="mono">{seconds(score?.rset)}</dd></div>
  </dl>

  {#if score?.recent_false_alarms?.length}
    <ul class="fooled">
      {#each score.recent_false_alarms as entry (entry.space + entry.at)}
        <li>
          <span class="tag">{entry.cause}</span>
          <span>{nameOf(entry.space)}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
  .card {
    background: #0d1420; border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 8px; text-align: center;
  }
  .card strong { display: block; font-size: 22px; line-height: 1.1; }
  .card span { font-size: 11px; color: var(--muted); }
  .good strong { color: #4ade80; }
  .bad.lit { border-color: #7f1d1d; }
  .bad.lit strong { color: #f87171; }
  .warn.lit { border-color: #78350f; }
  .warn.lit strong { color: #fbbf24; }
  .latency { margin: 12px 0 0; display: grid; gap: 4px; }
  .latency div { display: flex; justify-content: space-between; font-size: 12px; }
  .latency dt { color: var(--muted); }
  .latency dd { margin: 0; }
  .fooled { list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 5px; }
  .fooled li {
    display: grid; grid-template-columns: 78px 1fr; gap: 8px; align-items: center;
    font-size: 12px; background: #0d1420; border: 1px solid var(--line);
    border-radius: 8px; padding: 5px 8px;
  }
  .tag {
    text-align: center; font-size: 11px; padding: 2px 6px; border-radius: 999px;
    background: #43230d; color: #fdba74;
  }
</style>
