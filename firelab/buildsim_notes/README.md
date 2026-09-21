# How firelab connects to BuildSim

BuildSim is the building. firelab is everything that happens in it. This note
explains the small part of BuildSim you need to know to see how the two fit,
and `layers.py` prints the same story from a running BuildSim so you can check
it against the real thing.

## BuildSim in one sentence

BuildSim is one Go program that holds a building in memory and shows it in a
browser. It has no fire, no smoke, no people and no clock of its own. Whatever
firelab writes into it stays exactly as written until firelab writes again.

## The four layers

Think of BuildSim as four layers stacked on top of each other. firelab only
ever talks to the outer ones.

**1. The map.** The floor plans are built into the program: three floors of
rooms, the doorways between them, and the stairs that join the floors. firelab
reads this once when it starts, turns it into its own list of rooms and
door-gated links, and never asks again. BuildSim never changes the map.

**2. The memory.** Everything that can change lives in one in-memory store:
the equipment tree with its sensors and actuators, the coloured room layers,
the fire and smoke effects, the alarm markers, the door states, the people, the
head counts, and one session per open viewer tab. Three things about it decide
how firelab behaves:

- There is no physics in it. That is why firelab owns all the simulation and
  BuildSim only shows the result.
- A write replaces the whole collection. Sending an empty list of effects
  removes every effect. That is why firelab always sends complete lists, and
  why an empty route is how a route line is erased.
- It forgets everything when the program stops. After a BuildSim restart,
  firelab has to send everything again, which is what the Reload button does.

**3. The doors and windows.** The REST API is how anyone reads or writes the
memory. Two parts of it matter to firelab. The route finder runs a shortest
path search over the doorways, across floors through the stairs, and it steps
around rooms whose door is closed. That is why firelab tells BuildSim about a
closed fire door as well as closing it in its own physics: BuildSim's own route
search, which the viewer uses, then keeps out of the sealed room. The session
API holds the two things BuildSim keeps per browser tab rather than per
building: the coloured room outlines and the drawn escape route.

**4. The loudspeaker.** Every write to the memory is pushed to the open viewer
tabs over a WebSocket. firelab never talks to the viewer. It writes to the
memory, and the loudspeaker tells every tab. A per-tab write, like the route,
goes only to that tab, and when a tab reconnects it is told the outlines and
route it had before.

## What that means for firelab

Every arrow between firelab and BuildSim in the report is firelab writing to
layer 2 through layer 3, and the viewer hearing about it through layer 4.
BuildSim starts nothing: it never calls firelab, never moves time forward, and
never decides anything. That is the seam the course keeps pointing at. The
building is on one side, and everything that senses, thinks and acts is on the
other. It is also why BuildSim is drawn grey and unmodified in every diagram.

## See it for yourself

With BuildSim running on port 9090:

```
cd firelab && .venv/bin/python buildsim_notes/layers.py
```

The script asks BuildSim one question per layer and prints what it found: the
floors and stairs in the map, what is in the memory right now, a route the
door-and-window layer computes, and the viewer tabs the loudspeaker is talking
to. If BuildSim is not running it prints the descriptions and says so.

The code is split the way the layers are: one small function asks about one
layer and returns a plain record, one function turns records into text, and
one function runs them in order. Nothing knows about more than its own job.

## Where to read more

- `buildingsim/pkg/README.md` describes the same four layers from the inside,
  and every package has a `diagram.mmd` beside it.
- `tutorials/buildsim.md` walks through the API with examples.
- `firelab/adapters/buildsim/` is the only firelab code that speaks to BuildSim:
  `transport.py` sends requests, `client.py` names every endpoint, and
  `viewer.py` handles the per-tab session.
