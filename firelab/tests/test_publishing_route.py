"""When the escape route is (re)sent to the viewer, and when it is taken down.

The viewer re-frames its camera on every route it receives, so an unchanged
route is not sent again. But "unchanged" has to mean unchanged *for that tab*:
a reloaded viewer has never seen it. And a send that failed was never drawn.
"""

import asyncio
import unittest
from types import SimpleNamespace

from firelab.app.engine import publishing
from firelab.domain import world as world_mod

ROUTE = [{"name": "ROOM", "level": "level0", "x": 0.0, "y": 0.0},
         {"name": "EXIT", "level": "level0", "x": 2.0, "y": 0.0}]


class FakeViewer:
    def __init__(self, session="tab-1"):
        self.session = session
        self.routes: list[tuple[str, dict]] = []
        self.fail = False

    async def session_id(self, now):
        return self.session

    async def put_highlights(self, session_id, highlights):
        pass

    async def put_route(self, session_id, route):
        if self.fail:
            raise RuntimeError("BuildSim went away")
        self.routes.append((session_id, route))


def engine(viewer):
    return SimpleNamespace(
        client=SimpleNamespace(viewer=viewer),
        world=world_mod.World(),
        evacuation=SimpleNamespace(display_route=list(ROUTE), display_level="level0"),
        last_route=None,
        last_highlights=None,
    )


async def publish(e):
    await asyncio.gather(*await publishing.session_writes(e, {}), return_exceptions=True)


class TestRoutePublishing(unittest.IsolatedAsyncioTestCase):
    async def test_an_unchanged_route_is_sent_once(self):
        viewer = FakeViewer()
        e = engine(viewer)
        await publish(e)
        await publish(e)
        self.assertEqual(len(viewer.routes), 1)

    async def test_a_new_viewer_tab_is_sent_the_route_it_never_had(self):
        viewer = FakeViewer()
        e = engine(viewer)
        await publish(e)
        viewer.session = "tab-2"  # the user reloaded the viewer
        await publish(e)
        self.assertEqual([s for s, _ in viewer.routes], ["tab-1", "tab-2"])

    async def test_a_failed_send_is_tried_again(self):
        viewer = FakeViewer()
        e = engine(viewer)
        viewer.fail = True
        await publish(e)
        viewer.fail = False
        await publish(e)
        self.assertEqual(len(viewer.routes), 1)

    async def test_a_cleared_route_erases_the_line_once(self):
        viewer = FakeViewer()
        e = engine(viewer)
        await publish(e)
        e.evacuation.display_route, e.evacuation.display_level = [], ""
        await publish(e)
        await publish(e)
        self.assertEqual(len(viewer.routes), 2)
        self.assertEqual(viewer.routes[-1][1]["path"], [])

    async def test_nothing_is_sent_when_there_never_was_a_route(self):
        viewer = FakeViewer()
        e = engine(viewer)
        e.evacuation.display_route, e.evacuation.display_level = [], ""
        await publish(e)
        self.assertEqual(viewer.routes, [])


if __name__ == "__main__":
    unittest.main()
