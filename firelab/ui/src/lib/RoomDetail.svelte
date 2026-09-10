<script>
  import { store, api } from './store.svelte.js';
  import Chart from './Chart.svelte';

  let { selected = '' } = $props();

  // History is too big for the snapshot, so it is polled while a room is open.
  let points = $state([]);
  let terms = $state([]);
  const space = $derived((store.snapshot?.spaces ?? []).find((s) => s.key === selected));
  const clock = $derived(store.snapshot?.clock);

  $effect(() => {
    const key = selected;
    if (!key) {
      points = [];
      terms = [];
      return;
    }
    let alive = true;
    const load = () =>
      api
        .history(key)
        .then((data) => {
          if (!alive) return; // the user moved on: this answer is for a room nobody is watching
          points = data.points;
          terms = data.why;
        })
        .catch(() => {});
    load();
    // Slower when paused: nothing is changing, so there is nothing to catch up with.
    const timer = setInterval(load, clock?.running ? 2000 : 6000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  });

  // A history row is [t, temp, smoke, co, temp_read, smoke_read, co_read, p_fire]:
  // truth first, then what the sensors made of it.
  const column = (index) => points.map((p) => p[index]);

  // Largest contribution first, so the reason for the verdict is the top bar.
  const why = $derived([...terms].sort((a, b) => b.weighted - a.weighted));
  const span = $derived(Math.max(1, ...why.map((t) => Math.abs(t.weighted))));
</script>

<section class="panel detail">
  <h2>Room detail</h2>
  {#if !space}
    <p class="muted small">Select a room in the table to see its history and its verdict.</p>
  {:else}
    <p class="hint">
      <strong>{space.name}</strong> · {space.level} · {points.length} samples
    </p>

    <div class="split">
      <div class="charts">
        <Chart
          label="Smoke — truth vs reading"
          unit=" 1/m"
          series={[
            { name: 'truth', color: '#94a3b8', points: column(2) },
            { name: 'reading', color: '#38bdf8', points: column(5) }
          ]}
        />
        <Chart
          label="Temperature — truth vs reading"
          unit=" °C"
          series={[
            { name: 'truth', color: '#94a3b8', points: column(1) },
            { name: 'reading', color: '#f97316', points: column(4) }
          ]}
        />
        <Chart
          label="CO — truth vs reading"
          unit=" ppm"
          series={[
            { name: 'truth', color: '#94a3b8', points: column(3) },
            { name: 'reading', color: '#a78bfa', points: column(6) }
          ]}
        />
        <Chart
          label="P(fire)"
          series={[{ name: 'belief', color: '#f43f5e', points: column(7) }]}
        />
      </div>

      <div class="why">
        <h3>Why {Math.round(space.p_fire * 100)}%</h3>
        <p class="hint">
          Contributions to the {store.snapshot?.detector} score. Positive pushes towards fire.
        </p>
        {#if why.length}
          <ul class="terms">
            {#each why as term (term.name)}
              <li>
                <span class="name">{term.name.replace(/_/g, ' ')}</span>
                <span class="track">
                  <i
                    class:negative={term.weighted < 0}
                    style="width:{(Math.abs(term.weighted) / span) * 50}%;
                           {term.weighted < 0 ? 'right:50%' : 'left:50%'}"
                  ></i>
                </span>
                <span class="mono value" title="raw value {term.value}">
                  {term.weighted > 0 ? '+' : ''}{term.weighted.toFixed(2)}
                </span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="muted small">No readings in this room yet.</p>
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  .detail { flex: 0 1 auto; max-height: 46%; overflow: auto; }
  .split { display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr) minmax(240px, 300px); }
  .charts { display: grid; gap: 4px 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  h3 {
    margin: 0 0 4px; font-size: 12px; text-transform: uppercase; letter-spacing: .07em;
    color: var(--muted); font-weight: 600;
  }
  .small { font-size: 12px; }
  .terms { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 5px; }
  .terms li {
    display: grid; grid-template-columns: 104px 1fr 46px; align-items: center; gap: 8px;
    font-size: 12px;
  }
  .name { color: var(--muted); text-transform: capitalize; }
  .track {
    position: relative; height: 9px; border-radius: 4px; background: #0d1420;
    border: 1px solid var(--line);
  }
  .track::after {
    content: ''; position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: #334155;
  }
  .track i { position: absolute; top: 1px; bottom: 1px; background: #f43f5e; border-radius: 3px; }
  .track i.negative { background: #38bdf8; }
  .value { text-align: right; }
  @media (max-width: 1400px) {
    .detail { max-height: none; }
  }
  @media (max-width: 1100px) {
    .split, .charts { grid-template-columns: minmax(0, 1fr); }
  }
</style>
