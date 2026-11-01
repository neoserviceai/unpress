# Builder AI Module
# Provides AI-powered creative generation for Frappe Builder pages
#
# This module implements direct LLM generation with full creative freedom.
# The AI generates unique, context-adapted websites while respecting
# the FrappeBlock JSON format.
#
# NOTHING is imported eagerly here, on purpose.
#
# This package used to pull its own submodules at import time — providers,
# generators, validators. Every one of them imports `unpress_core.ai.logging`,
# which re-enters this file, which is halfway through importing providers. A
# single-threaded import survives that by luck of ordering; two requests
# importing at once do not, and Python raises either
#
#     ImportError: cannot import name 'get_provider' from partially
#     initialized module 'unpress_core.ai.providers' (circular import)
#
# or, from the other thread, `_frozen_importlib._DeadlockError`.
#
# It showed as the AI settings panel announcing "CLI not installed" for a CLI
# that was installed and paired: the first two calls after a restart raced each
# other, both failed, and the screen believed the empty answer.
#
# `__getattr__` (PEP 562) keeps the same public surface while importing each
# name only when someone asks for it, by which time the package is fully
# initialised.

__version__ = "2.0.0"

_EXPORTS = {
	"AIConfig": "unpress_core.ai.config",
	"get_ai_settings": "unpress_core.ai.config",
	"get_provider": "unpress_core.ai.providers",
	"PageGenerator": "unpress_core.ai.generators.page_generator",
	"generate_page": "unpress_core.ai.generators.page_generator",
	"BlockValidator": "unpress_core.ai.validators",
	"get_theme": "unpress_core.ai.design_system",
	"list_themes": "unpress_core.ai.design_system",
	"DESIGN_TOKENS": "unpress_core.ai.design_system",
	"ai_log": "unpress_core.ai.logging",
	"get_log_path": "unpress_core.ai.logging",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
	"""Import on first use — see the note above about the circular import."""
	module_path = _EXPORTS.get(name)
	if not module_path:
		raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

	import importlib

	value = getattr(importlib.import_module(module_path), name)
	globals()[name] = value  # later lookups skip this function entirely
	return value


def __dir__():
	return sorted(set(list(globals()) + __all__))
