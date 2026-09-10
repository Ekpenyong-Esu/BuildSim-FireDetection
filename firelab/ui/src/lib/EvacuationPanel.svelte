<script>
  import { store } from './store.svelte.js';

  const evac = $derived(store.snapshot?.evacuation);
  const counts = $derived(store.snapshot?.counts);
</script>

<section class="panel">
  <h2>Evacuation</h2>
  <p class="hint">Who is still in the building, floor by floor.</p>

  {#if evac?.levels?.length}
    <table>
      <thead>
        <tr><th>Floor</th><th>Inside</th><th>Moving</th><th>Stranded</th><th>Out</th></tr>
      </thead>
      <tbody>
        {#each evac.levels as row (row.level)}
          <tr>
            <td>{row.level}</td>
            <td class="mono">{row.inside}</td>
            <td class="mono moving">{row.evacuating || ''}</td>
            <td class="mono" class:stranded={row.stranded}>{row.stranded || ''}</td>
            <td class="mono out">{row.safe || ''}</td>
          </tr>
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <td>total</td>
          <td class="mono">{counts?.occupants - counts?.safe}</td>
          <td class="mono">{counts?.evacuating}</td>
          <td></td>
          <td class="mono">{counts?.safe}</td>
        </tr>
      </tfoot>
    </table>
  {:else}
    <p class="muted small">Nobody placed yet.</p>
  {/if}

  {#if evac?.stranded?.length}
    <p class="warn">
      No route out for {evac.stranded.length}: {evac.stranded.map((p) => p.room).join(', ')}
    </p>
  {/if}
</section>

<style>
  table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
  th {
    text-align: right; font-weight: 600; font-size: 10px; text-transform: uppercase;
    letter-spacing: .06em; color: var(--muted); padding-bottom: 4px;
  }
  th:first-child, td:first-child { text-align: left; }
  td { text-align: right; padding: 3px 0; border-top: 1px solid var(--line); }
  tfoot td { color: var(--muted); }
  .moving { color: #fbbf24; }
  .out { color: #4ade80; }
  .stranded { color: #f87171; }
  .warn {
    margin: 10px 0 0; font-size: 12px; color: #fca5a5;
    background: #1c0f12; border: 1px solid #7f1d1d; border-radius: 8px; padding: 6px 8px;
  }
  .small { font-size: 12px; }
</style>
