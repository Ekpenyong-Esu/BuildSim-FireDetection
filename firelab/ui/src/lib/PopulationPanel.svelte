<script>
  import { store, api } from './store.svelte.js';

  // A local copy, so typing is not overwritten by the next snapshot. It is only
  // sent when Apply is pressed, which is also when people are scattered again.
  let draft = $state({});
  let busy = $state(false);

  $effect(() => {
    if (store.config?.population && Object.keys(draft).length === 0) {
      draft = { ...store.config.population };
    }
  });

  const total = $derived(Object.values(draft).reduce((sum, n) => sum + (Number(n) || 0), 0));
  const live = $derived(store.snapshot?.population ?? []);
  // Apply is pointless until something differs from what the engine is running.
  const dirty = $derived(
    store.config?.population &&
      store.roles.some((r) => Number(draft[r.key] ?? 0) !== (store.config.population[r.key] ?? 0))
  );

  async function apply() {
    busy = true;
    try {
      const config = await api.putPopulation(
        Object.fromEntries(store.roles.map((r) => [r.key, Number(draft[r.key]) || 0]))
      );
      store.config = config;
    } finally {
      busy = false;
    }
  }

  function statusOf(key) {
    return live.find((row) => row.key === key);
  }
</script>

<section class="panel">
  <h2>Population</h2>
  <p class="hint">
    Who is in the building. Roles differ in how fast they find their way out, so the mix changes
    the evacuation time as much as the count does.
  </p>

  <table>
    <thead>
      <tr><th>Role</th><th>Count</th><th>Speed</th><th>Out</th></tr>
    </thead>
    <tbody>
      {#each store.roles as role (role.key)}
        {@const row = statusOf(role.key)}
        <tr>
          <td title={role.note}>{role.label}</td>
          <td>
            <input type="number" min="0" max="2000" bind:value={draft[role.key]} />
          </td>
          <td class="mono muted">{role.speed.toFixed(2)}×</td>
          <td class="mono">{row ? `${row.safe}/${row.total}` : '—'}</td>
        </tr>
      {/each}
    </tbody>
  </table>

  <div class="row">
    <span class="hint">{total} people in total</span>
    <button class="primary" disabled={busy || !dirty} onclick={apply}>
      {busy ? '…' : 'Apply & scatter'}
    </button>
  </div>
  <p class="hint">Applying re-places everyone, including those already evacuated.</p>
</section>

<style>
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { text-align: left; font-weight: 500; color: var(--muted); padding-bottom: 4px; }
  td { padding: 2px 0; }
  th:not(:first-child), td:not(:first-child) { text-align: right; width: 66px; }
  input { width: 62px; text-align: right; }
  .row { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
  .muted { color: var(--muted); }
</style>
