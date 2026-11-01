"""
Codex CLI provider — text and structured generation through a ChatGPT plan.

Why: `codex exec` runs the agent headlessly against the machine's Codex login
(a ChatGPT Plus/Pro session), so generation costs subscription usage instead of
metered API tokens. It also speaks JSON Schema natively (`--output-schema`),
which is exactly the contract our generators need.

SECURITY — read before touching this file. Codex is an *agent*: by design it
can run shell commands. Our prompts carry text that came from an LLM or from a
client's WordPress site, so a prompt injection could try to make it act. Every
invocation therefore:
  * runs with `--sandbox read-only` (text) — no writes anywhere;
  * runs `--ephemeral` (no session files) and `--skip-git-repo-check`;
  * passes the prompt on **stdin**, never through a shell (argv list, no
    shell=True), so nothing can be interpolated into a command line;
  * runs inside a dedicated empty working directory;
  * is killed on a hard timeout.
Never add `--dangerously-bypass-approvals-and-sandbox` here.

Images are the one exception, and a narrow one: drawing needs a writable
directory, so they run `--sandbox workspace-write` — and, where that sandbox
cannot start at all, `danger-full-access`. That only happens inside a
container, whose own boundary is stricter than the one we gave up. It is still
a widening: the working directory is a throwaway that holds nothing but the
generated file, and it is deleted when the call returns.

SCOPE — a ChatGPT plan is nominative. This provider is meant for a self-hosted
Studio driven by its own owner (or our own dogfooding), not as a shared backend
serving third parties.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

import frappe

from .base import BaseProvider

# Probed once per process: the answer cannot change while we run.
_SANDBOX_HELPER_WORKS = None


def _sandbox_helper_works() -> bool:
	"""Can Codex's filesystem sandbox actually run on this machine?

	On Linux it is enforced by a helper that needs an unprivileged user
	namespace. Docker's default seccomp profile blocks that syscall, so the
	helper dies while copying the finished image out — and Codex answers with
	the file name it *meant* to write, leaving the workspace empty. A caller
	sees a plausible success and no picture.

	macOS uses Seatbelt, which has no such requirement.
	"""
	global _SANDBOX_HELPER_WORKS
	if _SANDBOX_HELPER_WORKS is not None:
		return _SANDBOX_HELPER_WORKS
	if sys.platform != "linux":
		_SANDBOX_HELPER_WORKS = True
		return True
	try:
		probe = subprocess.run(
			[sys.executable, "-c", "import os; os.unshare(os.CLONE_NEWUSER)"],
			capture_output=True,
			timeout=15,
		)
		_SANDBOX_HELPER_WORKS = probe.returncode == 0
	except Exception:
		_SANDBOX_HELPER_WORKS = False
	return _SANDBOX_HELPER_WORKS


class CodexProvider(BaseProvider):
	"""Talk to the Codex CLI instead of an HTTP API."""

	# No default model on purpose: a ChatGPT plan only accepts the models the
	# plan itself exposes ("The 'gpt-5.5-codex' model is not supported when
	# using Codex with a ChatGPT account"), so we let the CLI pick unless the
	# site explicitly names one.
	DEFAULT_MODEL = None
	DEFAULT_TIMEOUT = 900

	# How hard the model thinks before answering. Codex exposes this as a
	# config override rather than a flag; it is the single biggest lever on
	# both quality and wall-clock, so it belongs in the Studio next to the
	# model rather than buried in site_config.
	REASONING_EFFORTS = ("minimal", "low", "medium", "high")

	def __init__(
		self,
		model: str = None,
		api_key: str = None,
		base_url: str = None,
		temperature: float = 0.7,
		max_tokens: int = None,
		timeout: int = None,
		reasoning_effort: str = None,
		**kwargs,
	):
		self.reasoning_effort = (
			reasoning_effort or frappe.conf.get("codex_reasoning_effort") or ""
		).strip().lower() or None
		if self.reasoning_effort and self.reasoning_effort not in self.REASONING_EFFORTS:
			self.reasoning_effort = None
		super().__init__(
			model=model or frappe.conf.get("codex_model") or self.DEFAULT_MODEL,
			api_key=api_key,
			base_url=base_url,
			temperature=temperature,
			max_tokens=max_tokens,
			timeout=timeout or self.DEFAULT_TIMEOUT,
			**kwargs,
		)

	# ------------------------------------------------------------------
	# plumbing
	# ------------------------------------------------------------------

	@property
	def provider_name(self) -> str:
		return "codex"

	@staticmethod
	def binary() -> Optional[str]:
		"""Absolute path to the codex binary, honouring an explicit setting.

		A bench started by supervisor/docker rarely inherits the shell PATH that
		nvm installs into, so the path is configurable per site.
		"""
		configured = frappe.conf.get("codex_binary")
		if configured and os.path.isfile(configured):
			return configured
		found = shutil.which("codex")
		if found:
			return found
		# common nvm / npm global locations, newest first
		candidates = []
		home = os.path.expanduser("~")
		nvm = os.path.join(home, ".nvm", "versions", "node")
		if os.path.isdir(nvm):
			for version in sorted(os.listdir(nvm), reverse=True):
				candidates.append(os.path.join(nvm, version, "bin", "codex"))
		candidates += ["/usr/local/bin/codex", "/opt/homebrew/bin/codex", os.path.join(home, ".local", "bin", "codex")]
		for candidate in candidates:
			if os.path.isfile(candidate):
				return candidate
		return None

	@classmethod
	def _env(cls) -> dict:
		"""Minimal environment. CODEX_HOME holds the login, so it must survive
		across bench restarts and belong to the bench user."""
		env = {
			"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
			"HOME": os.environ.get("HOME", os.path.expanduser("~")),
			"LANG": "C.UTF-8",
		}
		codex_home = frappe.conf.get("codex_home")
		if codex_home:
			env["CODEX_HOME"] = codex_home
		return env

	@staticmethod
	def enabled_here() -> bool:
		"""Is Codex allowed on THIS site?

		Same reason as codex_api._only_admin: CODEX_HOME is per bench, not per
		site, so a shared bench must not let one tenant's plan serve the others.
		"""
		return bool(frappe.utils.cint(frappe.conf.get("codex_enabled")))

	@classmethod
	def login_status(cls) -> tuple[bool, str]:
		"""(logged_in, human message) — never raises."""
		if not cls.enabled_here():
			return False, "Codex is not enabled on this site (codex_enabled)"
		binary = cls.binary()
		if not binary:
			return False, "Codex CLI not found (install it, or set codex_binary)"
		try:
			proc = subprocess.run(
				[binary, "login", "status"],
				capture_output=True,
				text=True,
				timeout=30,
				env=cls._env(),
			)
		except Exception as e:
			return False, f"Could not run the Codex CLI: {e}"
		out = f"{proc.stdout}\n{proc.stderr}".strip()
		lowered = out.lower()
		# careful: "Not logged in" contains "logged in" — check the negative first
		logged_in = "logged in" in lowered and "not logged in" not in lowered
		return logged_in, (out.splitlines()[0] if out else "No answer from the CLI")

	def is_available(self) -> bool:
		ok, _ = self.login_status()
		return ok

	# ------------------------------------------------------------------
	# generation
	# ------------------------------------------------------------------

	@classmethod
	def _strict_schema(cls, node):
		"""A JSON Schema the structured-output endpoint will accept.

		It insists on additionalProperties: false and on every property being
		listed in `required`. Pydantic emits neither, so a model with defaults
		came back as HTTP 400 and the call looked like the model had simply
		refused to answer. Defaults still apply on our side: the schema only
		says the model must emit the key, and validation fills the rest.

		It also STRIPS every `default`. Requiring the key was not enough: pydantic
		writes `"default": "#6366f1"` next to each property, and the model reads
		that as the expected answer. Measured on a brief for a wine estate: 16 of
		18 chrome fields came back byte-identical to their default — indigo and
		violet for a vineyard, the same header, the same footer, the same band, on
		every site. A default is our fallback, not a suggestion to the model, and
		it has no business travelling in the schema.
		"""
		if isinstance(node, list):
			return [cls._strict_schema(item) for item in node]
		if not isinstance(node, dict):
			return node

		out = {
			key: cls._strict_schema(value)
			for key, value in node.items()
			if key != "default"
		}

		# `$ref` tolerates no company. Pydantic writes the field's description
		# beside it — {"$ref": "#/$defs/TypographyScale", "description": "..."} —
		# and the endpoint answers 400. The reference carries the shape; the
		# prose belongs to the field it came from and is lost here on purpose.
		if "$ref" in out:
			return {"$ref": out["$ref"]}
		if out.get("type") == "object" or "properties" in out:
			properties = out.get("properties") or {}
			out["additionalProperties"] = False
			out["required"] = list(properties.keys())
		return out

	@staticmethod
	def _local_images(images: list = None) -> list:
		"""Site file URLs turned into paths the CLI can open.

		Without this the model is asked about a picture it was never given,
		and answers nothing — which is exactly how it failed before.
		"""
		if not images:
			return []
		from frappe.utils.file_manager import get_file_path

		paths = []
		for image in images:
			if not image:
				continue
			try:
				# "/files/x.png" is a site URL, not a path — and it looks
				# absolute, so test for a real file before trusting it.
				path = image if os.path.isfile(image) else get_file_path(image)
			except Exception:
				continue
			# frappe answers relative to the sites directory, and the CLI runs
			# in a scratch dir of ours — a relative path resolves to nothing
			# there, which reads exactly like a model that ignored the image.
			path = os.path.abspath(path)
			if os.path.isfile(path):
				paths.append(path)
		return paths

	def _run(self, prompt: str, schema: dict = None, timeout: int = None, images: list = None) -> str:
		from unpress_core.ai.logging import ai_log

		binary = self.binary()
		if not binary:
			raise RuntimeError("Codex CLI not found on this server")

		# an empty scratch dir: nothing of ours is reachable even if the agent
		# tried to look around
		with tempfile.TemporaryDirectory(prefix="unpress-codex-") as workdir:
			answer_path = os.path.join(workdir, "answer.txt")
			argv = [
				binary,
				"exec",
				"--sandbox",
				"read-only",
				"--ephemeral",
				"--skip-git-repo-check",
				"--ignore-user-config",
				"--color",
				"never",
				"-C",
				workdir,
				"-o",
				answer_path,
			]
			if self.model:
				argv += ["-m", self.model]
			if self.reasoning_effort:
				argv += ["-c", f'model_reasoning_effort="{self.reasoning_effort}"']
			for path in self._local_images(images):
				argv += ["-i", path]
			if schema:
				schema_path = os.path.join(workdir, "schema.json")
				with open(schema_path, "w", encoding="utf-8") as f:
					json.dump(self._strict_schema(schema), f)
				argv += ["--output-schema", schema_path]
			argv.append("-")  # prompt on stdin

			ai_log(
				"info",
				"codex exec",
				model=self.model,
				reasoning=self.reasoning_effort,
				structured=bool(schema),
				prompt_chars=len(prompt or ""),
				images=len(images or []),
			)
			try:
				proc = subprocess.run(
					argv,
					input=prompt or "",
					capture_output=True,
					text=True,
					timeout=timeout or self.timeout,
					env=self._env(),
					cwd=workdir,
				)
			except subprocess.TimeoutExpired:
				raise RuntimeError(f"Codex timed out after {timeout or self.timeout}s")

			if os.path.isfile(answer_path):
				with open(answer_path, encoding="utf-8") as f:
					answer = f.read().strip()
				if answer:
					return answer

			detail = (proc.stderr or proc.stdout or "").strip().splitlines()
			raise RuntimeError(
				f"Codex returned no answer (exit {proc.returncode})"
				+ (f": {detail[-1][:300]}" if detail else "")
			)

	def generate(
		self,
		prompt: str,
		system_prompt: str = None,
		temperature: float = None,
		max_tokens: int = None,
		images: list = None,
		**kwargs,
	) -> str:
		# temperature/max_tokens have no equivalent on the CLI — the plan's
		# model settings apply.
		full = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
		return self._run(full, timeout=kwargs.get("timeout"), images=images)

	def generate_structured(
		self,
		prompt: str,
		schema,
		system_prompt: str = None,
		temperature: float = None,
		images: list = None,
		**kwargs,
	):
		"""Return a validated instance of the Pydantic `schema`.

		Codex takes a JSON Schema file and enforces the shape itself, so there
		is no "please answer in JSON" prompt-begging here.
		"""
		json_schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema
		full = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
		raw = self._run(full, schema=json_schema, timeout=kwargs.get("timeout"), images=images)

		try:
			data = json.loads(raw)
		except json.JSONDecodeError:
			# belt and braces: the CLI can wrap the payload in prose or a fence
			from json_repair import repair_json

			start, end = raw.find("{"), raw.rfind("}")
			candidate = raw[start : end + 1] if start != -1 and end > start else raw
			data = json.loads(repair_json(candidate))

		return schema.model_validate(data) if hasattr(schema, "model_validate") else data

	# ------------------------------------------------------------------
	# images
	# ------------------------------------------------------------------

	def generate_image_file(
		self, prompt: str, width: int = 1024, height: int = 1024, timeout: int = None
	) -> bytes:
		"""Generate one image and return its bytes.

		Images need a writable workspace, so the sandbox is widened to
		`workspace-write` — scoped to a throwaway directory that holds nothing
		but the generated file. Where that sandbox cannot run at all (see
		`_sandbox_helper_works`) we widen further rather than fail: a container
		is already the boundary the sandbox would have drawn.

		There is no image-model argument on purpose. Codex's `-m` picks the
		agent that *drives* the drawing tool, not the model that draws, and a
		ChatGPT plan rejects an image model there outright:
		"'gpt-image-1' is not supported when using Codex with a ChatGPT
		account". The drawing model is the plugin's business.
		"""
		from unpress_core.ai.logging import ai_log

		binary = self.binary()
		if not binary:
			raise RuntimeError("Codex CLI not found on this server")

		import time as _time

		started_at = _time.time() - 5
		with tempfile.TemporaryDirectory(prefix="unpress-codex-img-") as workdir:
			instruction = (
				f"Generate one photorealistic image, {width}x{height} pixels (landscape if wider than tall): "
				f"{prompt}\n\n"
				"Save it as a PNG file directly in the current working directory. "
				"No text, letters, logos or watermarks anywhere in the image. "
				"Answer with the file name only."
			)
			# NOT --ignore-user-config here: the image tool is exposed through
			# the skills/plugins declared in CODEX_HOME/config.toml, and
			# ignoring that config leaves the agent with no way to draw.
			sandbox = "workspace-write" if _sandbox_helper_works() else "danger-full-access"
			argv = [
				binary,
				"exec",
				"--sandbox",
				sandbox,
				"--ephemeral",
				"--skip-git-repo-check",
				"--color",
				"never",
				"-C",
				workdir,
			]
			if self.model:
				argv += ["-m", self.model]
			if self.reasoning_effort:
				argv += ["-c", f'model_reasoning_effort="{self.reasoning_effort}"']
			argv.append("-")

			ai_log(
				"info",
				"codex image",
				w=width,
				h=height,
				model=self.model,
				sandbox=sandbox,
				prompt=(prompt or "")[:60],
			)
			try:
				proc = subprocess.run(
					argv,
					input=instruction,
					capture_output=True,
					text=True,
					timeout=timeout or self.DEFAULT_TIMEOUT,
					env=self._env(),
					cwd=workdir,
				)
			except subprocess.TimeoutExpired:
				raise RuntimeError("Codex image generation timed out")

			images = [
				os.path.join(root, name)
				for root, _dirs, files in os.walk(workdir)
				for name in files
				if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
			]
			if not images:
				# also look where the CLI stores its own renders
				codex_home = self._env().get("CODEX_HOME") or os.path.join(
					os.path.expanduser("~"), ".codex"
				)
				gallery = os.path.join(codex_home, "generated_images")
				if os.path.isdir(gallery):
					recent = [
						os.path.join(root, name)
						for root, _dirs, files in os.walk(gallery)
						for name in files
						if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
						and os.path.getmtime(os.path.join(root, name)) > started_at
					]
					images = recent
			if not images:
				tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
				raise RuntimeError(
					"Codex produced no image file"
					+ (f": {tail[-1][:300]}" if tail else "")
				)
			# biggest file = the actual render, not a thumbnail
			best = max(images, key=os.path.getsize)
			with open(best, "rb") as f:
				return f.read()
