import unittest
from pathlib import Path


class WebMemberSwitchTest(unittest.TestCase):
    def test_switch_actor_updates_the_visible_member_select(self):
        html = (Path(__file__).resolve().parents[1] / "HDZB_agent" / "index.html").read_text()
        start = html.index("async function switchActor(name)")
        end = html.index("async function addMember", start)
        switch_actor = html[start:end]

        self.assertIn("actorName=name", switch_actor)
        self.assertIn("el('member').value=name", switch_actor)
        self.assertIn("当前聊天：${name}", switch_actor)


if __name__ == "__main__":
    unittest.main()
