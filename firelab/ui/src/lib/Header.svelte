<script>
  import { store, api } from './store.svelte.js';

  const snapshot = $derived(store.snapshot);
  const clock = $derived(snapshot?.clock);
  const buildsim = $derived(snapshot?.buildsim);

  let factor = $state(1);
  // A local copy of the speed, so dragging the slider is not fought by incoming
  // snapshots. It is only sent to the server when the drag ends.
  $effect(() => {
    if (clock) factor = clock.factor;
  });
</script>

<header>
  <div class="brand">
    <span class="flame"></span>
    <div>
      <h1>firelab</h1>
      <p>fire detection &amp; autonomous response</p>
    </div>
  </div>

  <div class="row">
    <span class="pill">
      <span class="dot" class:ok={buildsim?.connected} class:bad={buildsim && !buildsim.connected}
      ></span>
      BuildSim {buildsim?.connected ? 'online' : 'offline'}
    </span>
    <span class="pill">{buildsim?.spaces ?? 0} spaces</span>
    <span class="pill">
      <span class="dot" class:ok={store.live} class:bad={!store.live}></span>
      {store.live ? 'live' : 'reconnecting'}
    </span>
  </div>

  <div class="row controls">
    <span class="clock mono">{clock?.text ?? '--:--:--'}</span>
    <button class="primary" onclick={() => api.clock({ running: !clock?.running })}>
      {clock?.running ? 'Pause' : 'Run'}
    </button>
    <label class="speed">
      <input
        type="range"
        min="1"
        max="60"
        step="1"
        bind:value={factor}
        onchange={() => api.clock({ factor })}
      />
      <span class="mono">{factor}×</span>
    </label>
    <button onclick={() => api.reload()}>Reload floors</button>
    <a class="button-ish" href="/api/export.csv" download>Export CSV</a>
    <button class="danger" onclick={() => api.reset()}>Reset</button>
    <a class="pill link" href={buildsim?.url ?? '#'} target="_blank" rel="noreferrer">
      3D viewer ↗
    </a>
  </div>
</header>

{#if store.error}
  <div class="error">{store.error}</div>
{/if}

<style>
  header {
    display: flex; align-items: center; justify-content: space-between;
    gap: 16px; flex-wrap: wrap;
    padding: 14px 20px; margin-bottom: 16px;
    background: linear-gradient(180deg, #131b28, #0d1420);
    border: 1px solid var(--line); border-radius: var(--radius);
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .flame {
    width: 12px; height: 12px; border-radius: 3px;
    background: linear-gradient(180deg, #fbbf24, #ef4444);
    box-shadow: 0 0 14px #ef444488;
  }
  h1 { margin: 0; font-size: 17px; letter-spacing: .02em; }
  p { margin: 0; font-size: 12px; color: var(--muted); }
  .controls { gap: 10px; }
  .clock { font-size: 18px; letter-spacing: .06em; }
  .speed { display: flex; align-items: center; gap: 8px; width: 170px; }
  .link { text-decoration: none; color: var(--accent); }
  .button-ish {
    display: inline-flex; align-items: center; text-decoration: none;
    background: #1e293b; color: var(--text); border: 1px solid var(--line);
    border-radius: 8px; padding: 6px 12px; font-size: 13px;
  }
  .button-ish:hover { border-color: var(--accent); }
  .error {
    margin-bottom: 12px; padding: 9px 14px; border-radius: 10px;
    background: #3b1414; border: 1px solid #7f1d1d; font-size: 13px;
  }
</style>
