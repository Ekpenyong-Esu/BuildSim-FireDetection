<script>
  import { store } from './store.svelte.js';
  import DeviceList from './DeviceList.svelte';

  let { selected = $bindable('') } = $props();

  let onlyActive = $state(false);
  let level = $state('all');
  let expanded = $state(''); // the one room showing its individual devices

  const levels = $derived([...new Set(store.rooms.map((r) => r.level))].sort());

  // A room with no sensor produces no readings, so it is not in the snapshot at all.
  const monitored = $derived(store.snapshot?.spaces ?? []);

  const perLevel = $derived(
    Object.fromEntries(
      levels.map((name) => [name, monitored.filter((s) => s.level === name).length])
    )
  );

  const spaces = $derived(
    monitored
      .filter((s) => level === 'all' || s.level === level)
      .filter((s) => !onlyActive || s.state !== 'NORMAL' || s.p_fire > 0.1)
      // Most suspicious first, so the interesting room finds the user.
      .sort((a, b) => b.p_fire - a.p_fire || a.name.localeCompare(b.name))
  );

  function fmt(value, digits = 1) {
    return value === null || value === undefined ? '—' : value.toFixed(digits);
  }
</script>

<section class="panel table-panel">
  <div class="head">
    <div>
      <h2>Rooms</h2>
      <p class="hint">
        Only rooms with sensors appear here — {monitored.length} of {store.rooms.length}. Simulated
        truth on the left, what the sensors report in the middle, what the system believes on the
        right. Divergence between them is the whole exercise.
      </p>
    </div>
    <label class="row filter">
      <select bind:value={level} aria-label="floor">
        <option value="all">all floors</option>
        {#each levels as name (name)}
          <option value={name}>{name} ({perLevel[name] ?? 0})</option>
        {/each}
      </select>
      <input type="checkbox" bind:checked={onlyActive} /> only active
    </label>
  </div>

  <div class="scroll body">
    <table>
      <thead>
        <tr>
          <th>Room</th>
          <th colspan="3">Truth</th>
          <th colspan="3">Reading</th>
          <th>P(fire)</th>
          <th>State</th>
          <th>Response</th>
        </tr>
        <tr class="sub">
          <th></th>
          <th>°C</th><th>smoke</th><th>ppm</th>
          <th>°C</th><th>smoke</th><th>ppm</th>
          <th></th><th></th><th></th>
        </tr>
      </thead>
      <tbody>
        {#each spaces as space (space.key)}
          <tr
            class:selected={selected === space.key}
            onclick={() => {
              selected = space.key;
              expanded = expanded === space.key ? '' : space.key;
            }}
          >
            <td>
              <strong>{space.name}</strong>
              <span class="muted level">{space.level}</span>
            </td>
            <td class="mono">{fmt(space.truth.temperature)}</td>
            <td class="mono">{fmt(space.truth.smoke, 3)}</td>
            <td class="mono">{fmt(space.truth.co, 0)}</td>
            <td class="mono read">{fmt(space.reading.temperature)}</td>
            <td class="mono read">{fmt(space.reading.smoke, 3)}</td>
            <td class="mono read">{fmt(space.reading.co, 0)}</td>
            <td>
              <div class="row">
                <div class="bar"><span style="width:{space.p_fire * 100}%"></span></div>
                <span class="mono pct">{Math.round(space.p_fire * 100)}%</span>
              </div>
            </td>
            <td><span class="state {space.state}">{space.state}</span></td>
            <td class="icons">
              {#if space.sprinkler}<span title="sprinkler active">💧</span>{/if}
              {#if space.door !== 'open'}<span title="door closed">🚪</span>{/if}
              {#if space.occupants}<span title="occupants">{space.occupants}👤</span>{/if}
            </td>
          </tr>
          {#if expanded === space.key}
            <tr class="devices">
              <td colspan="10"><DeviceList devices={space.devices} /></td>
            </tr>
          {/if}
        {:else}
          <tr>
            <td colspan="10" class="muted empty">
              Deploy sensors and ignite a source to populate this table.
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .table-panel { display: flex; flex-direction: column; min-height: 0; padding-bottom: 8px; }
  .head { display: flex; gap: 16px; justify-content: space-between; align-items: flex-start; }
  .filter { font-size: 12px; color: var(--muted); white-space: nowrap; }
  .body { flex: 1; min-height: 0; }
  tr { cursor: pointer; }
  tr.selected td { background: #17263a; }
  .sub th { top: 26px; font-size: 10px; }
  .level { margin-left: 6px; font-size: 11px; }
  .read { color: var(--accent); }
  .pct { font-size: 12px; width: 34px; text-align: right; }
  .icons { white-space: nowrap; font-size: 12px; }
  .empty { text-align: center; padding: 28px 0; }
  .devices td { background: #0d1420; }
</style>
