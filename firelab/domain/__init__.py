"""The basic simulation rules used by Firelab.

The app engine calls these files on every tick. Adapters connect them to
BuildSim and the UI. These files do not use the network, the browser, or a
real clock, so they are easy to test. The main flow is
``sources -> physics -> sensing -> features -> detector -> agent -> interlocks``
with people, safety, scoring, timing, and history watching the run.
"""
