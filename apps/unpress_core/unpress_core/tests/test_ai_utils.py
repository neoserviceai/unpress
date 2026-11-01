"""
Tests for AI Utils Module
Tests for unpress_core.ai.utils
"""

import unittest
from unpress_core.ai.utils import (
    KEBAB_TO_CAMEL,
    VALID_ELEMENTS,
    kebab_to_camel,
    generate_block_id,
    ensure_unique_ids,
    convert_styles_to_camel,
    validate_element,
    deep_merge,
)


class TestKebabToCamel(unittest.TestCase):
    """Tests for kebab_to_camel function"""

    def test_known_property(self):
        """Test conversion of known CSS property"""
        self.assertEqual(kebab_to_camel("background-color"), "backgroundColor")
        self.assertEqual(kebab_to_camel("flex-direction"), "flexDirection")
        self.assertEqual(kebab_to_camel("border-radius"), "borderRadius")

    def test_unknown_property(self):
        """Test conversion of unknown CSS property"""
        self.assertEqual(kebab_to_camel("custom-property"), "customProperty")
        self.assertEqual(kebab_to_camel("my-custom-style"), "myCustomStyle")

    def test_single_word(self):
        """Test single word without hyphens"""
        self.assertEqual(kebab_to_camel("color"), "color")
        self.assertEqual(kebab_to_camel("padding"), "padding")


class TestGenerateBlockId(unittest.TestCase):
    """Tests for generate_block_id function"""

    def test_default_prefix(self):
        """Test block ID with default prefix"""
        block_id = generate_block_id()
        self.assertTrue(block_id.startswith("block-"))
        self.assertEqual(len(block_id), 14)  # block- (6) + 8 hex chars

    def test_custom_prefix(self):
        """Test block ID with custom prefix"""
        block_id = generate_block_id("hero")
        self.assertTrue(block_id.startswith("hero-"))

    def test_uniqueness(self):
        """Test that generated IDs are unique"""
        ids = [generate_block_id() for _ in range(100)]
        self.assertEqual(len(ids), len(set(ids)))


class TestEnsureUniqueIds(unittest.TestCase):
    """Tests for ensure_unique_ids function"""

    def test_missing_block_id(self):
        """Test that missing blockId is generated"""
        block = {"element": "div"}
        result = ensure_unique_ids(block)
        self.assertIn("blockId", result)
        self.assertTrue(result["blockId"].startswith("div-"))

    def test_duplicate_block_id(self):
        """Test that duplicate blockIds are fixed"""
        block = {
            "blockId": "test-id",
            "element": "div",
            "children": [
                {"blockId": "test-id", "element": "span"}
            ]
        }
        result = ensure_unique_ids(block)
        self.assertEqual(result["blockId"], "test-id")
        self.assertNotEqual(result["children"][0]["blockId"], "test-id")

    def test_preserves_unique_ids(self):
        """Test that unique blockIds are preserved"""
        block = {
            "blockId": "unique-id",
            "element": "div",
            "children": [
                {"blockId": "child-id", "element": "span"}
            ]
        }
        result = ensure_unique_ids(block)
        self.assertEqual(result["blockId"], "unique-id")
        self.assertEqual(result["children"][0]["blockId"], "child-id")


class TestConvertStylesToCamel(unittest.TestCase):
    """Tests for convert_styles_to_camel function"""

    def test_kebab_conversion(self):
        """Test conversion of kebab-case properties"""
        styles = {
            "background-color": "#fff",
            "font-size": "16px",
        }
        result = convert_styles_to_camel(styles)
        self.assertEqual(result["backgroundColor"], "#fff")
        self.assertEqual(result["fontSize"], "16px")

    def test_camel_preserved(self):
        """Test that camelCase properties are preserved"""
        styles = {
            "backgroundColor": "#fff",
            "fontSize": "16px",
        }
        result = convert_styles_to_camel(styles)
        self.assertEqual(result, styles)

    def test_numeric_values(self):
        """Test that numeric values are converted to strings"""
        styles = {"opacity": 0.5, "zIndex": 10}
        result = convert_styles_to_camel(styles)
        self.assertEqual(result["opacity"], "0.5")
        self.assertEqual(result["zIndex"], "10")

    def test_none_values_excluded(self):
        """Test that None values are excluded"""
        styles = {"color": "#000", "background": None}
        result = convert_styles_to_camel(styles)
        self.assertIn("color", result)
        self.assertNotIn("background", result)

    def test_empty_input(self):
        """Test empty or invalid input"""
        self.assertEqual(convert_styles_to_camel({}), {})
        self.assertEqual(convert_styles_to_camel(None), {})
        self.assertEqual(convert_styles_to_camel("invalid"), {})


class TestValidateElement(unittest.TestCase):
    """Tests for validate_element function"""

    def test_valid_elements(self):
        """Test valid HTML elements"""
        valid = ["div", "section", "header", "footer", "p", "a", "button", "img"]
        for element in valid:
            self.assertTrue(validate_element(element), f"{element} should be valid")

    def test_invalid_elements(self):
        """Test invalid HTML elements"""
        invalid = ["custom", "widget", "component", "block"]
        for element in invalid:
            self.assertFalse(validate_element(element), f"{element} should be invalid")


class TestDeepMerge(unittest.TestCase):
    """Tests for deep_merge function"""

    def test_simple_merge(self):
        """Test simple dictionary merge"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_nested_merge(self):
        """Test nested dictionary merge"""
        base = {"styles": {"color": "red", "padding": "10px"}}
        override = {"styles": {"color": "blue"}}
        result = deep_merge(base, override)
        self.assertEqual(result["styles"]["color"], "blue")
        self.assertEqual(result["styles"]["padding"], "10px")

    def test_preserves_original(self):
        """Test that original dictionaries are not modified"""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = deep_merge(base, override)
        self.assertNotIn("c", base["a"])
        self.assertEqual(base["a"], {"b": 1})


class TestConstants(unittest.TestCase):
    """Tests for module constants"""

    def test_kebab_to_camel_completeness(self):
        """Test that KEBAB_TO_CAMEL contains common properties"""
        expected = [
            "background-color",
            "font-size",
            "flex-direction",
            "justify-content",
            "align-items",
            "border-radius",
        ]
        for prop in expected:
            self.assertIn(prop, KEBAB_TO_CAMEL)

    def test_valid_elements_completeness(self):
        """Test that VALID_ELEMENTS contains common elements"""
        expected = [
            "div", "section", "header", "footer", "nav",
            "h1", "h2", "p", "span", "a", "button", "img",
            "ul", "li", "form", "input",
        ]
        for element in expected:
            self.assertIn(element, VALID_ELEMENTS)


if __name__ == "__main__":
    unittest.main()
