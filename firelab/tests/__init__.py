"""The test suite.

Four kinds of test, in rough order of how much they cover:

    test_<module>.py   one domain module's mechanics in isolation
    test_evacuation.py the router, with BuildSim faked
    test_presets.py    one end-to-end run per preset: does it keep its promise?
    test_layering.py   the dependency rules, checked with `ast` rather than trusted

Nothing here needs a service running. That is the practical payoff of keeping
`domain/` pure, and `test_layering.py` is what stops it quietly lapsing.
"""
