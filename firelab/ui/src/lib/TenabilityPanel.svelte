<script>
  import { store } from './store.svelte.js';

  const ten = $derived(store.snapshot?.tenability);
</script>

<section class="panel" class:alarm={ten?.exposed}>
  <h2>Life safety</h2>
  <p class="hint">
    Rooms that have stopped being escapable, by the ISO 13571 thresholds: 60 °C, or smoke thick
    enough to drop visibility below 10 m.
  </p>

  <div class="cards">
    <div class="card" class:lit={ten?.exposed}>
      <strong>{ten?.exposed ?? 0}</strong>
      <span>people exposed</span>
    </div>
    <div class="card" class:lit={ten?.incapacitated}>
      <strong>{ten?.incapacitated ?? 0}</strong>
      <span>over CO dose</span>
    </div>
    <div class="card muted">
      <strong>{ten?.untenable_count ?? 0}</strong>
      <span>rooms lost</span>
    </div>
  </div>

  <p class="hint dose">
    Worst dose taken <span class="mono" class:over={ten && ten.worst_fed >= ten.fed_limit}>
      {((ten?.worst_fed ?? 0) * 100).toFixed(0)}%
    </span>
    of an incapacitating one. Doses are kept after people get out.
  </p>

  {#if ten?.untenable_rooms?.length}
    <ul>
      {#each ten.untenable_rooms as room (room.key)}
        <li>
          <span class="name">{room.name}</span>
          <span class="muted small">{room.level}</span>
          <span class="reason">{room.reason}</span>
          {#if room.occupants}<span class="heads">{room.occupants}👤</span>{/if}
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted small">Every room is still escapable.</p>
  {/if}
</section>

<style>
  .alarm { border-color: #b91c1c; }
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0 8px; }
  .card {
    background: #0d1420; border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 6px; text-align: center;
  }
  .card strong { display: block; font-size: 20px; }
  .card span { font-size: 10px; color: var(--muted); }
  .card.lit { border-color: #b91c1c; background: #2a1111; }
  .card.lit strong { color: #f87171; }
  .card.muted strong { color: var(--muted); }
  .dose { margin: 6px 0 2px; }
  .dose .over { color: #f87171; }
  ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 3px; max-height: 150px; overflow: auto; }
  li { display: flex; align-items: baseline; gap: 6px; font-size: 12px; }
  .name { flex: 1; }
  .reason { color: #fbbf24; font-variant-numeric: tabular-nums; }
  .heads { color: #f87171; }
  .small { font-size: 10px; }
  .muted { color: var(--muted); }
</style>
