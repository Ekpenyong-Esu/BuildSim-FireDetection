<script>
  import { api } from './store.svelte.js';

  // Breaking a sensor is its own story to tell, so it lives in its own file
  // rather than inside the room table's markup.
  let { devices = [] } = $props();

  const FAULTS = ['none', 'stuck', 'dropout', 'drift', 'dead'];
</script>

{#if devices.length}
  <div class="row">
    {#each devices as device (device.id)}
      <div class="device">
        <span class="modality">{device.modality}</span>
        <span class="mono">{device.reading ?? '—'}</span>
        <!-- Changing this breaks the sensor mid-run, without pausing. -->
        <select
          value={device.fault}
          onchange={(e) => api.fault({ device_id: device.id, fault: e.currentTarget.value })}
        >
          {#each FAULTS as fault (fault)}
            <option value={fault}>{fault}</option>
          {/each}
        </select>
      </div>
    {/each}
  </div>
{:else}
  <span class="muted">No devices deployed in this room.</span>
{/if}

<style>
  .device {
    display: flex; align-items: center; gap: 8px;
    background: #111a27; border: 1px solid var(--line); border-radius: 8px; padding: 5px 8px;
  }
  .device select { width: auto; padding: 3px 6px; font-size: 12px; }
  .modality { font-size: 12px; color: var(--muted); text-transform: capitalize; }
</style>
