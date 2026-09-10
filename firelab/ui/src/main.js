// The one entry point Vite builds from: attach App to the empty div in index.html.
import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';

export default mount(App, { target: document.getElementById('app') });
