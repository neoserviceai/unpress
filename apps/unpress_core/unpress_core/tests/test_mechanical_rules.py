"""Mechanical safety-net rules of BlockValidator (R1 root-flex, R2 ghost text)."""

import unittest

from unpress_core.ai.validators.block_validator import BlockValidator


def _section(children=None, styles=None):
	return {
		"blockId": "sec1",
		"element": "section",
		"baseStyles": {"display": "flex", **(styles or {})},
		"children": children or [],
	}


def _wide(bid):
	return {"blockId": bid, "element": "div", "baseStyles": {}, "children": []}


class TestRootFlexRule(unittest.TestCase):
	def test_forces_column_on_wide_children(self):
		blocks = [_section(children=[_wide("a"), _wide("b")])]
		out = BlockValidator().validate_and_repair(blocks)
		self.assertEqual(out[0]["baseStyles"]["flexDirection"], "column")

	def test_respects_explicit_direction(self):
		blocks = [_section(children=[_wide("a"), _wide("b")], styles={"flexDirection": "row"})]
		out = BlockValidator().validate_and_repair(blocks)
		self.assertEqual(out[0]["baseStyles"]["flexDirection"], "row")

	def test_ignores_narrow_children(self):
		narrow = {"blockId": "n", "element": "div", "baseStyles": {"width": "40%"}, "children": []}
		blocks = [_section(children=[narrow, dict(narrow, blockId="n2")])]
		out = BlockValidator().validate_and_repair(blocks)
		self.assertNotIn("flexDirection", out[0]["baseStyles"])


class TestGhostTextRule(unittest.TestCase):
	def _ghost(self, opacity=None, font="120px"):
		styles = {"position": "absolute", "fontSize": font}
		if opacity is not None:
			styles["opacity"] = opacity
		return {
			"blockId": "ghost",
			"element": "span",
			"innerHTML": "Pain au Feu",
			"baseStyles": styles,
			"children": [],
		}

	def test_caps_opacity_and_sends_behind(self):
		blocks = [_section(children=[self._ghost(opacity="0.4")], styles={"flexDirection": "column"})]
		out = BlockValidator().validate_and_repair(blocks)
		ghost = out[0]["children"][0]
		self.assertEqual(ghost["baseStyles"]["opacity"], "0.08")
		self.assertEqual(ghost["baseStyles"]["zIndex"], "-1")

	def test_rem_font_sizes_count(self):
		blocks = [_section(children=[self._ghost(font="8rem")], styles={"flexDirection": "column"})]
		out = BlockValidator().validate_and_repair(blocks)
		self.assertEqual(out[0]["children"][0]["baseStyles"]["zIndex"], "-1")

	def test_leaves_normal_absolute_text_alone(self):
		normal = {
			"blockId": "badge",
			"element": "span",
			"innerHTML": "Nouveau",
			"baseStyles": {"position": "absolute", "fontSize": "14px"},
			"children": [],
		}
		blocks = [_section(children=[normal], styles={"flexDirection": "column"})]
		out = BlockValidator().validate_and_repair(blocks)
		self.assertNotIn("zIndex", out[0]["children"][0]["baseStyles"])

	def test_faded_ghost_still_forced_behind(self):
		blocks = [_section(children=[self._ghost(opacity="0.05")], styles={"flexDirection": "column"})]
		out = BlockValidator().validate_and_repair(blocks)
		ghost = out[0]["children"][0]
		self.assertEqual(ghost["baseStyles"]["opacity"], "0.05")
		self.assertEqual(ghost["baseStyles"]["zIndex"], "-1")


class TestPlaceholderTextRule(unittest.TestCase):
	def test_strips_text_from_large_placeholders(self):
		hero = {
			"blockId": "hero",
			"element": "section",
			"baseStyles": {
				"display": "flex",
				"flexDirection": "column",
				"background": 'linear-gradient(rgba(0,0,0,.5),rgba(0,0,0,.3)), url("https://placehold.co/1200x600/2B1B12/F5EDE3?text=Pain+au+feu+de+bois")',
			},
			"children": [],
		}
		out = BlockValidator().validate_and_repair([hero])
		bg = out[0]["baseStyles"]["background"]
		self.assertIn("placehold.co/1200x600/2B1B12/2B1B12", bg)
		self.assertNotIn("?text=", bg)

	def test_keeps_avatar_initials(self):
		avatar = {
			"blockId": "av",
			"element": "img",
			"baseStyles": {},
			"attributes": {"src": "https://placehold.co/80x80/2B1B12/ffffff?text=JD"},
			"children": [],
		}
		out = BlockValidator().validate_and_repair([avatar])
		self.assertIn("?text=JD", out[0]["attributes"]["src"])


if __name__ == "__main__":
	unittest.main()
