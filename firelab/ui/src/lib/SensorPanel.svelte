<script>
  import { store, api } from './store.svelte.js';

  const MODALITIES = ['smoke', 'co', 'temperature'];

  let query = $state('');
  let level = $state('all');
  let chosen = $state(new Set()); // room keys ticked for the next deploy
  let modalities = $state(['smoke', 'co', 'temperature']);
  let busy = $state(false);

  const levels = $derived([...new Set(store.rooms.map((r) => r.level))].sort());

  const matches = $derived(
    store.rooms
      .filter((r) => level === 'all' || r.level === level)
      .filter((r) => !query || `${r.level} ${r.name}`.toLowerCase().includes(query.toLowerCase()))
  );

  const counts = $derived(store.snapshot?.counts);

  function toggle(key) {
    // Replaced rather than mutated: reactivity is triggered by assignment, not by add().
    const next = new Set(chosen);
    next.has(key) ? next.delete(key) : next.add(key);
    chosen = next;
  }

  function toggleModality(modality) {
    modalities = modalities.includes(modality)
      ? modalities.filter((m) => m !== modality)
      : [...modalities, modality];
  }

  // 'deploy' and 'undeploy' take the same arguments, so one function covers both buttons.
  async function run(action) {
    busy = true;
    try {
      await api[action]({ spaces: [...chosen], modalities });
    } finally {
      busy = false; // released even on failure, or the panel would lock up
    }
  }

  function selectVisible() {
    chosen = new Set(matches.map((r) => r.key));
  }

  function selectNone() {
    chosen = new Set();
  }
</script>

<section class="panel">
  <h2>Sensor deployment</h2>
  <p class="hint">
    {counts?.devices ?? 0} devices deployed · {counts?.faulty ?? 0} faulty. Devices are mirrored
    into BuildSim as equipment.
  </p>

  <div class="field">
    <label for="sensor-search">Rooms</label>
    <div class="row">
      <input id="sensor-search" placeholder="Filter rooms…" bind:value={query} />
      <select bind:value={level} aria-label="floor">
        <option value="all">all</option>
        {#each levels as name (name)}
          <option value={name}>{name}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="list scroll">
    {#each matches as room (room.key)}
      <label class="item">
        <input type="checkbox" checked={chosen.has(room.key)} onchange={() => toggle(room.key)} />
        <span>{room.name}</span>
        <span class="muted">{room.level} · {room.area} m²</span>
      </label>
    {/each}
  </div>

  {#if matches.length}
    <p class="hint cap">{matches.length} rooms match · {chosen.size} selected</p>
  {/if}

  <div class="row modalities">
    {#each MODALITIES as modality (modality)}
      <label class="chip" class:on={modalities.includes(modality)}>
        <input
          type="checkbox"
          checked={modalities.includes(modality)}
          onchange={() => toggleModality(modality)}
        />
        {modality}
      </label>
    {/each}
  </div>

  <div class="row actions">
    <button class="ghost" onclick={selectVisible}>Select all ({matches.length})</button>
    <button class="ghost" onclick={selectNone}>Clear</button>
    <button class="primary" disabled={busy || !chosen.size || !modalities.length} onclick={() => run('deploy')}>
      Deploy {chosen.size ? `(${chosen.size})` : ''}
    </button>
    <button class="danger" disabled={busy || !chosen.size} onclick={() => run('undeploy')}>
      Remove
    </button>
  </div>
</section>

<style>
  .list {
    max-height: 210px; border: 1px solid var(--line); border-radius: 10px;
    background: #0d1420; padding: 4px; margin-bottom: 12px;
  }
  .cap { margin: -8px 0 12px; }
  .item {
    display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center;
    padding: 5px 8px; border-radius: 7px; font-size: 13px; cursor: pointer;
  }
  .item:hover { background: #16202f; }
  .modalities { margin-bottom: 12px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 999px; font-size: 12px; cursor: pointer;
    border: 1px solid var(--line); background: #0d1420; color: var(--muted);
  }
  .chip.on { border-color: var(--accent); color: var(--text); }
  .actions { justify-content: flex-end; }
</style>
