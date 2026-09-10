<script>
  // A search box over 956 rooms: a plain dropdown would be unusable at that size.
  // `value` is bindable so the parent owns the chosen room key.
  let { rooms = [], value = $bindable(''), placeholder = 'Search rooms…' } = $props();

  let query = $state('');
  let open = $state(false);

  const matches = $derived(
    query
      ? rooms.filter((r) => `${r.level} ${r.name}`.toLowerCase().includes(query.toLowerCase()))
      : rooms
  );

  const selected = $derived(rooms.find((r) => r.key === value));

  function pick(room) {
    value = room.key;
    query = '';
    open = false;
  }
</script>

<div class="picker">
  <!-- Closing on blur is delayed: a click on the list has to land before it disappears. -->
  <input
    {placeholder}
    value={open ? query : selected ? `${selected.level} · ${selected.name}` : query}
    oninput={(e) => {
      query = e.currentTarget.value;
      open = true;
    }}
    onfocus={() => (open = true)}
    onblur={() => setTimeout(() => (open = false), 150)}
  />
  {#if open}
    <ul class="scroll">
      {#each matches as room (room.key)}
        <li>
          <button type="button" class="ghost" onclick={() => pick(room)}>
            <span>{room.name}</span>
            <span class="muted">{room.level} · {room.kind} · {room.area} m²</span>
          </button>
        </li>
      {:else}
        <li class="muted empty">No match</li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .picker { position: relative; }
  ul {
    position: absolute; z-index: 20; top: calc(100% + 4px); left: 0; right: 0;
    max-height: 240px; margin: 0; padding: 4px; list-style: none;
    background: #0d1420; border: 1px solid var(--line); border-radius: 10px;
    box-shadow: 0 18px 40px rgba(0, 0, 0, .55);
  }
  li button {
    display: flex; justify-content: space-between; gap: 12px; width: 100%;
    border: none; border-radius: 7px; padding: 6px 9px; text-align: left;
  }
  li button:hover { background: #16202f; }
  .empty { padding: 8px 10px; font-size: 12px; }
</style>
