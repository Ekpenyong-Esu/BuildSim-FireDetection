<script>
  import { store } from './store.svelte.js';

  // Reversed so the newest decision is at the top, where it will be read.
  const entries = $derived([...(store.snapshot?.journal ?? [])].reverse());

  // Simulated time is seconds since the run began; show it as a clock face.
  function time(t) {
    const seconds = Math.floor(t % 86400);
    const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
    const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
    const s = String(seconds % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
  }
</script>

<section class="panel journal">
  <h2>Journal</h2>
  <div class="scroll list">
    {#each entries as entry, index (index)}
      <div class="entry">
        <span class="mono time">{time(entry.t)}</span>
        <span class="kind {entry.kind}">{entry.kind}</span>
        <span>{entry.message}</span>
      </div>
    {:else}
      <span class="muted">Nothing has happened yet.</span>
    {/each}
  </div>
</section>

<style>
  .journal { display: flex; flex-direction: column; min-height: 0; }
  .list { flex: 1; min-height: 0; max-height: 260px; display: grid; gap: 4px; align-content: start; }
  .entry {
    display: grid; grid-template-columns: 66px 74px 1fr; gap: 8px; align-items: baseline;
    font-size: 12px; padding: 3px 0; border-bottom: 1px solid #16202f;
  }
  .time { color: var(--muted); }
  .kind {
    font-size: 10px; text-transform: uppercase; letter-spacing: .05em;
    padding: 1px 6px; border-radius: 999px; background: #182231; color: var(--muted);
    text-align: center;
  }
  .kind.agent { background: #10304a; color: #7dd3fc; }
  .kind.actuator { background: #123322; color: #86efac; }
  .kind.interlock { background: #43230d; color: #fdba74; }
  .kind.error { background: #4c1414; color: #fecaca; }
  .kind.scenario { background: #2a1840; color: #d8b4fe; }
</style>
