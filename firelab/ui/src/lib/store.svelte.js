// Single source of truth for the UI: one SSE stream in, small commands out.

// $state makes this reactive: any component that reads it re-renders on its own,
// so nothing has to subscribe and nothing keeps a second copy.
export const store = $state({
  snapshot: null, // the whole simulation, replaced wholesale on every event
  rooms: [], // the room list, fetched once and never changed by the engine
  presets: [],
  roles: [],
  config: null,
  live: false, // false means the event stream dropped and the screen is frozen
  error: ''
});

// Every request goes through here, so there is one place that reports failure.
async function call(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    store.error = `${method} ${path}: ${response.status}`;
    throw new Error(store.error);
  }
  store.error = '';
  return response.status === 204 ? null : response.json();
}

// One function per endpoint. These are the only ways the interface can change anything.
export const api = {
  clock: (body) => call('POST', '/api/clock', body),
  reset: () => call('POST', '/api/reset'),
  reload: () => call('POST', '/api/reload'),
  ignite: (body) => call('POST', '/api/scenario/ignite', body),
  preset: (body) => call('POST', '/api/scenario/preset', body),
  extinguish: (id) => call('DELETE', `/api/scenario/${id}`),
  history: (space) => call('GET', `/api/history?space=${encodeURIComponent(space)}`),
  deploy: (body) => call('POST', '/api/sensors/deploy', body),
  undeploy: (body) => call('POST', '/api/sensors/undeploy', body),
  fault: (body) => call('POST', '/api/sensors/fault', body),
  mode: (auto) => call('POST', '/api/agent/mode', { auto }),
  command: (body) => call('POST', '/api/actuators/command', body),
  putConfig: (patch) => call('PUT', '/api/config', patch),
  putPopulation: (population) => call('PUT', '/api/population', { population })
};

// Fetch the things that never change, then open the stream that carries everything else.
export async function bootstrap() {
  store.rooms = await call('GET', '/api/rooms');
  store.presets = await call('GET', '/api/presets');
  store.roles = await call('GET', '/api/roles');
  store.config = await call('GET', '/api/config');

  // The server pushes; the browser never polls for state.
  const source = new EventSource('/api/events');
  source.onmessage = (event) => {
    store.snapshot = JSON.parse(event.data);
    store.live = true;
  };
  source.onerror = () => {
    store.live = false;
  };
  return () => source.close(); // the caller closes the stream on teardown
}

export async function refreshRooms() {
  store.rooms = await call('GET', '/api/rooms');
}
