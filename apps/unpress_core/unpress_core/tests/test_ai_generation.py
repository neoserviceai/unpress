"""
Tests for AI Site Generation
Tests for builder.api generate_site and webshop templates
"""

import unittest
import json






class TestHeaderSchemaDefaults(unittest.TestCase):
    """Tests for header schema default values"""





class TestNavigationLinks(unittest.TestCase):
    """Tests for navigation link generation"""




class TestBlockStructure(unittest.TestCase):
    """Tests for generated block structure validity"""






class TestLayoutSanitizer(unittest.TestCase):
    """Tests for _sanitize_layout_styles — strips flex-only props when the
    block is display:grid, and grid-only props when the block is display:flex.
    """

    def _run(self, blocks):
        # Instantiate the generator without __init__ to avoid provider /
        # database setup — we only need the method under test.
        from unpress_core.ai.generators.page_generator import PageGenerator
        gen = PageGenerator.__new__(PageGenerator)
        return gen._sanitize_layout_styles(blocks)

    def test_flex_block_drops_grid_props(self):
        blocks = [{
            "blockId": "b1",
            "element": "section",
            "baseStyles": {
                "display": "flex",
                "flexDirection": "row",
                "gap": "24px",
                "gridTemplateColumns": "repeat(4, 1fr)",
                "gridAutoRows": "200px",
            },
        }]
        out = self._run(blocks)[0]["baseStyles"]
        self.assertEqual(out["display"], "flex")
        self.assertEqual(out["flexDirection"], "row")
        self.assertEqual(out["gap"], "24px")
        self.assertNotIn("gridTemplateColumns", out)
        self.assertNotIn("gridAutoRows", out)

    def test_grid_block_drops_flex_props(self):
        blocks = [{
            "blockId": "b1",
            "element": "section",
            "baseStyles": {
                "display": "grid",
                "gridTemplateColumns": "repeat(3, 1fr)",
                "gap": "20px",
                "flexDirection": "row",
                "flexWrap": "wrap",
            },
        }]
        out = self._run(blocks)[0]["baseStyles"]
        self.assertEqual(out["display"], "grid")
        self.assertEqual(out["gridTemplateColumns"], "repeat(3, 1fr)")
        self.assertNotIn("flexDirection", out)
        self.assertNotIn("flexWrap", out)

    def test_mobile_styles_cleaned_using_base_display(self):
        # mobileStyles has no display but inherits display: flex from base.
        # The orphan gridTemplateColumns must be stripped.
        blocks = [{
            "blockId": "b1",
            "element": "div",
            "baseStyles": {"display": "flex", "flexDirection": "row"},
            "mobileStyles": {"gridTemplateColumns": "1fr"},
        }]
        out = self._run(blocks)[0]
        self.assertNotIn("gridTemplateColumns", out["mobileStyles"])

    def test_children_are_walked(self):
        blocks = [{
            "blockId": "parent",
            "element": "section",
            "baseStyles": {"display": "block"},
            "children": [{
                "blockId": "child",
                "element": "div",
                "baseStyles": {
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "flexWrap": "wrap",
                },
            }],
        }]
        out = self._run(blocks)[0]["children"][0]["baseStyles"]
        self.assertEqual(out["gridTemplateColumns"], "1fr 1fr")
        self.assertNotIn("flexWrap", out)

    def test_no_display_means_no_stripping(self):
        blocks = [{
            "blockId": "b1",
            "element": "p",
            "baseStyles": {"padding": "20px"},
        }]
        out = self._run(blocks)[0]["baseStyles"]
        self.assertEqual(out, {"padding": "20px"})


if __name__ == "__main__":
    unittest.main()
