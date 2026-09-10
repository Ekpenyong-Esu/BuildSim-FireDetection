<script>
  import { store, api } from './store.svelte.js';
  import RoomPicker from './RoomPicker.svelte';

  // The five things that can be lit. The last three are nuisances: they look like a
  // fire to at least one sensor, which is exactly what makes them worth simulating.
  const KINDS = [
    { id: 'flaming', label: 'Flaming fire', note: 'heat + smoke + CO' },
    { id: 'smouldering', label: 'Smouldering fire', note: 'little heat, dense smoke, high CO' },
    { id: 'cooking', label: 'Cooking', note: 'nuisance: smoke, warm, low CO' },
    { id: 'dust', label: 'Dust', note: 'nuisance: smoke only' },
    { id: 'steam', label: 'Steam', note: 'nuisance: smoke only' }
  ];

  let space = $state('');
  let kind = $state('flaming');
  let growth = $state('medium');
  let delay = $state(0);
  let peak = $state(2000);

  const sources = $derived(store.snapshot?.sources ?? []);
  const note = $derived(KINDS.find((k) => k.id === kind)?.note ?? '');
  let busy = $state('');

  async function runPreset(preset) {
    busy = preset.id;
    try {
      await api.preset({ preset: preset.id, space });
    } finally {
      busy = '';
    }
  }

  function nameOf(key) {
    return store.rooms.find((r) => r.key === key)?.name ?? key;
  }
</script>

<section class="panel">
  <h2>Scenario</h2>
  <p class="hint">Place an ignition source. Its kind is also the ground-truth label.</p>

  <div class="field">
    <label for="scenario-room">Room</label>
    <RoomPicker rooms={store.rooms} bind:value={space} placeholder="Search rooms…" />
  </div>

  <div class="presets">
    <span class="legend">Presets — instrument the room and its neighbours, then set the scene</span>
    {#each store.presets as preset (preset.id)}
      <button
        class="preset"
        disabled={!space || busy}
        title={preset.description}
        onclick={() => runPreset(preset)}
      >
        <strong>{busy === preset.id ? '…' : preset.name}</strong>
        <span>{preset.description}</span>
      </button>
    {/each}
  </div>

  <div class="field">
    <label for="scenario-kind">Source</label>
    <select id="scenario-kind" bind:value={kind}>
      {#each KINDS as option (option.id)}
        <option value={option.id}>{option.label}</option>
      {/each}
    </select>
    <span class="hint">{note}</span>
  </div>

  <div class="grid-2">
    {#if kind === 'flaming'}
      <div class="field">
        <label for="scenario-growth">Growth</label>
        <select id="scenario-growth" bind:value={growth}>
          {#each ['slow', 'medium', 'fast', 'ultrafast'] as option (option)}
            <option value={option}>{option}</option>
          {/each}
        </select>
      </div>
      <div class="field">
        <label for="scenario-peak">Peak (kW)</label>
        <input id="scenario-peak" type="number" min="50" step="50" bind:value={peak} />
      </div>
    {/if}
    <div class="field">
      <label for="scenario-delay">Start delay (s)</label>
      <input id="scenario-delay" type="number" min="0" step="10" bind:value={delay} />
    </div>
  </div>

  <button
    class="primary wide"
    disabled={!space}
    onclick={() => api.ignite({ space, kind, growth, delay: Number(delay), peak_kw: Number(peak) })}
  >
    Ignite
  </button>

  {#if sources.length}
    <ul class="sources">
      {#each sources as source (source.id)}
        <li>
          <span class="tag {source.kind}">{source.kind}</span>
          <span>{nameOf(source.space)}</span>
          <button class="ghost small" onclick={() => api.extinguish(source.id)}>remove</button>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .presets { display: grid; gap: 6px; margin: 4px 0 14px; }
  .legend { font-size: 11px; color: var(--muted); }
  .preset {
    display: grid; gap: 1px; text-align: left; padding: 7px 9px;
    background: #0d1420; border: 1px solid var(--line); border-radius: 8px; cursor: pointer;
  }
  .preset:hover:not(:disabled) { border-color: #38bdf8; }
  .preset:disabled { opacity: .45; cursor: not-allowed; }
  .preset strong { font-size: 12.5px; }
  .preset span { font-size: 11px; color: var(--muted); }
  .wide { width: 100%; margin-top: 4px; }
  .sources { list-style: none; margin: 14px 0 0; padding: 0; display: grid; gap: 6px; }
  .sources li {
    display: grid; grid-template-columns: 92px 1fr auto; align-items: center; gap: 8px;
    background: #0d1420; border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px;
    font-size: 13px;
  }
  .tag {
    font-size: 11px; text-align: center; padding: 2px 6px; border-radius: 999px;
    background: #1e293b; color: var(--muted);
  }
  .tag.flaming { background: #4c1414; color: #fecaca; }
  .tag.smouldering { background: #43230d; color: #fdba74; }
  .small { padding: 3px 8px; font-size: 12px; }
</style>
