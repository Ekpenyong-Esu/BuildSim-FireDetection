"""Timing constants shared by the tick loop and outbound publishing."""

REAL_TICK = 0.25  # seconds of wall clock between engine ticks
PUBLISH_EVERY = 1.0  # simulated seconds between BuildSim writes
MAX_SENSOR_WRITES = 24  # per publish, to keep BuildSim responsive
