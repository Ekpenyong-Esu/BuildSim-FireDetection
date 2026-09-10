<script>
  import { onMount } from 'svelte';
  import { bootstrap } from './lib/store.svelte.js';
  import Header from './lib/Header.svelte';
  import ScenarioPanel from './lib/ScenarioPanel.svelte';
  import SensorPanel from './lib/SensorPanel.svelte';
  import RoomTable from './lib/RoomTable.svelte';
  import RoomDetail from './lib/RoomDetail.svelte';
  import ResponsePanel from './lib/ResponsePanel.svelte';
  import Scorecard from './lib/Scorecard.svelte';
  import EvacuationPanel from './lib/EvacuationPanel.svelte';
  import PopulationPanel from './lib/PopulationPanel.svelte';
  import TenabilityPanel from './lib/TenabilityPanel.svelte';
  import SettingsPanel from './lib/SettingsPanel.svelte';
  import Journal from './lib/Journal.svelte';

  // The only state the interface owns itself: which room the user is looking at.
  // Everything else arrives from the server.
  let selected = $state('');

  onMount(() => {
    let close;
    bootstrap().then((fn) => (close = fn));
    return () => close?.(); // close the event stream if the page tears down
  });
</script>

<main>
  <Header />
  <div class="layout">
    <div class="column">
      <ScenarioPanel />
      <Scorecard />
      <EvacuationPanel />
      <PopulationPanel />
      <SensorPanel />
    </div>
    <div class="column center">
      <RoomTable bind:selected />
      <RoomDetail {selected} />
    </div>
    <div class="column">
      <ResponsePanel {selected} />
      <TenabilityPanel />
      <SettingsPanel />
      <Journal />
    </div>
  </div>
</main>

<style>
  main {
    max-width: 1800px; margin: 0 auto; padding: 18px 20px 26px;
    height: 100vh; display: flex; flex-direction: column;
  }
  .layout {
    flex: 1; min-height: 0;
    display: grid; gap: 16px;
    grid-template-columns: minmax(300px, 340px) minmax(0, 1fr) minmax(300px, 360px);
  }
  .column { display: flex; flex-direction: column; gap: 16px; min-height: 0; overflow: auto; }
  .center { overflow: hidden; }
  @media (max-width: 1400px) {
    main { height: auto; }
    .layout { grid-template-columns: minmax(280px, 1fr) minmax(0, 2fr); }
    .column { overflow: visible; }
  }
  @media (max-width: 980px) {
    .layout { grid-template-columns: 1fr; }
  }
</style>
