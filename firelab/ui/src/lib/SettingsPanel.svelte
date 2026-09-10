<script>
  import { store, api } from './store.svelte.js';

  // Local mirrors, so a slider is not yanked back by the next snapshot. They are
  // seeded once from the config and sent on release.
  let noise = $state(1);
  let interval = $state(5);
  let speed = $state(1.3);
  let seed = $state(1);
  let ready = $state(false);

  $effect(() => {
    if (store.config && !ready) {
      noise = store.config.sensors.noise_scale;
      interval = store.config.sensors.interval;
      speed = store.config.walking_speed;
      seed = store.config.seed;
      ready = true;
    }
  });

  const quality = $derived(noise <= 0.5 ? 'laboratory' : noise <= 1.5 ? 'realistic' : 'poor');

  function sensors(patch) {
    api.putConfig({ sensors: patch });
  }
</script>

<section class="panel">
  <h2>Simulation settings</h2>
  <p class="hint">
    The knobs that decide how hard the problem is. Changes take effect on the next tick; the seed
    only matters from the next reset.
  </p>

  <div class="field">
    <label for="set-noise">Sensor noise <span class="mono">{noise.toFixed(1)}×</span></label>
    <input
      id="set-noise"
      type="range"
      min="0"
      max="3"
      step="0.1"
      bind:value={noise}
      onchange={() => sensors({ noise_scale: Number(noise) })}
    />
    <span class="hint">0 is a perfect instrument, 3 is a badly behaved one — currently {quality}.</span>
  </div>

  <div class="field">
    <label for="set-interval">Sampling interval <span class="mono">{interval}s</span></label>
    <input
      id="set-interval"
      type="range"
      min="1"
      max="60"
      step="1"
      bind:value={interval}
      onchange={() => sensors({ interval: Number(interval) })}
    />
    <span class="hint">Longer saves radio power and battery, and costs detection latency.</span>
  </div>

  <div class="field">
    <label for="set-speed">Walking speed <span class="mono">{speed.toFixed(2)} m/s</span></label>
    <input
      id="set-speed"
      type="range"
      min="0.5"
      max="2"
      step="0.05"
      bind:value={speed}
      onchange={() => api.putConfig({ walking_speed: Number(speed) })}
    />
    <span class="hint">Before each role's own factor. 1.3 m/s is the usual design figure.</span>
  </div>

  <div class="field">
    <label for="set-seed">Random seed</label>
    <div class="row">
      <input
        id="set-seed"
        type="number"
        min="0"
        bind:value={seed}
        onchange={() => api.putConfig({ seed: Number(seed) })}
      />
      <span class="hint">Same seed, same run — quote it in your report.</span>
    </div>
  </div>
</section>

<style>
  .field { display: grid; gap: 3px; margin-bottom: 12px; }
  .field:last-child { margin-bottom: 0; }
  label { font-size: 11px; color: var(--muted); display: flex; gap: 6px; }
  label .mono { color: var(--fg); }
  .row { display: flex; align-items: center; gap: 8px; }
  .row input { width: 80px; }
</style>
