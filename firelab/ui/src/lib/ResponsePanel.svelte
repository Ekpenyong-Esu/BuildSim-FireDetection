<script>
  import { store, api } from './store.svelte.js';

  let { selected = '' } = $props();

  const snapshot = $derived(store.snapshot);
  const counts = $derived(snapshot?.counts);
  const space = $derived((snapshot?.spaces ?? []).find((s) => s.key === selected));
  const response = $derived(store.config?.response);

  let thresholds = $state({ investigate: 0.35, pre_alarm: 0.55, confirm: 0.75 });
  // Mirror the server's settings locally so the sliders stay under the user's finger.
  $effect(() => {
    if (response)
      thresholds = {
        investigate: response.investigate,
        pre_alarm: response.pre_alarm,
        confirm: response.confirm
      };
  });

  let verdict = $state('');

  // A manual command is checked by the same interlocks as an automatic one, and the
  // reason is shown either way: a refusal is as informative as an action.
  async function send(kind, value) {
    const result = await api.command({ kind, space: selected, value });
    verdict = `${result.allowed ? 'allowed' : 'blocked'} — ${result.reason}`;
  }

  function push() {
    api.putConfig({ response: { ...thresholds } });
  }
</script>

<section class="panel">
  <h2>Response</h2>
  <p class="hint">
    The agent proposes; the interlocks dispose. Water needs heat corroboration, fire doors never
    lock, and a room on an escape route cannot be sealed.
  </p>

  <label class="auto">
    <input
      type="checkbox"
      checked={snapshot?.auto ?? true}
      onchange={(e) => api.mode(e.currentTarget.checked)}
    />
    <span>Autonomous response</span>
  </label>

  <div class="stats">
    <div><strong>{counts?.alarms ?? 0}</strong><span>alarms</span></div>
    <div><strong>{counts?.evacuating ?? 0}</strong><span>evacuating</span></div>
    <div><strong>{counts?.safe ?? 0}</strong><span>safe</span></div>
    <div><strong>{counts?.occupants ?? 0}</strong><span>occupants</span></div>
  </div>

  <h3>Manual override</h3>
  {#if space}
    <p class="target">{space.name} <span class="state {space.state}">{space.state}</span></p>
    <div class="row">
      <button onclick={() => send('sprinkler', space.sprinkler ? 'off' : 'on')}>
        Sprinkler {space.sprinkler ? 'off' : 'on'}
      </button>
      <button onclick={() => send('fire_door', space.door === 'open' ? 'closed' : 'open')}>
        Door {space.door === 'open' ? 'close' : 'open'}
      </button>
      <button onclick={() => send('evacuate', 'start')}>Evacuate</button>
    </div>
    {#if verdict}<p class="verdict">{verdict}</p>{/if}
  {:else}
    <p class="muted small">Select a room in the table to command it directly.</p>
  {/if}

  <h3>Thresholds</h3>
  {#each [['investigate', 'Investigate'], ['pre_alarm', 'Pre-alarm'], ['confirm', 'Confirm']] as [key, label] (key)}
    <label class="slider">
      <span>{label}</span>
      <input
        type="range"
        min="0.05"
        max="0.95"
        step="0.05"
        bind:value={thresholds[key]}
        onchange={push}
      />
      <span class="mono">{Number(thresholds[key]).toFixed(2)}</span>
    </label>
  {/each}
</section>

<style>
  h3 {
    margin: 18px 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .07em;
    color: var(--muted); font-weight: 600;
  }
  .auto { display: flex; align-items: center; gap: 8px; font-size: 13px; }
  .stats {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 14px;
  }
  .stats div {
    background: #0d1420; border: 1px solid var(--line); border-radius: 10px;
    padding: 8px; text-align: center;
  }
  .stats strong { display: block; font-size: 18px; }
  .stats span { font-size: 11px; color: var(--muted); }
  .target { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; font-size: 13px; }
  .verdict { margin: 10px 0 0; font-size: 12px; color: var(--muted); }
  .small { font-size: 12px; }
  .slider {
    display: grid; grid-template-columns: 84px 1fr 42px; align-items: center; gap: 8px;
    font-size: 12px; color: var(--muted); margin-bottom: 6px;
  }
  .slider .mono { text-align: right; color: var(--text); }
</style>
