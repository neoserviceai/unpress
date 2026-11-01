# Builder AI Module

AI-powered page generation for Frappe Builder using a multi-pass pipeline architecture.

## Overview

The AI module provides intelligent page generation capabilities that create Frappe Builder-compatible blocks using LLM providers (OpenAI, Ollama). The system uses a template-based approach where AI generates content and templates provide structure, ensuring consistent, high-quality output.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PageGenerator                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PASS 1: ANALYSIS                                         │   │
│  │  • Parse user prompt                                      │   │
│  │  • Determine page structure                               │   │
│  │  • Select sections based on site type                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PASS 2: CONTEXT                                          │   │
│  │  • Load theme configuration                               │   │
│  │  • Prepare design tokens                                  │   │
│  │  • Retrieve RAG examples (if available)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PASS 3: GENERATION                                       │   │
│  │  ├── HeaderGenerator → Header block                       │   │
│  │  ├── SectionGenerator → Content sections                  │   │
│  │  └── FooterGenerator → Footer block                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PASS 4: VALIDATION                                       │   │
│  │  • BlockValidator checks structure                        │   │
│  │  • AutoFixer corrects common issues                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
builder/ai/
├── __init__.py           # Main exports
├── config.py             # AI configuration
├── utils.py              # Shared utilities
│
├── providers/            # LLM Provider implementations
│   ├── base.py           # BaseProvider abstract class
│   ├── openai_provider.py
│   └── ollama_provider.py
│
├── generators/           # Content generators
│   ├── page_generator.py    # Main orchestrator
│   ├── section_generator.py # Section generation
│   ├── header_generator.py  # Header generation
│   └── footer_generator.py  # Footer generation
│
├── templates/            # Block templates
│   ├── headers.py        # Header templates
│   ├── footers.py        # Footer templates
│   └── sections.py       # Section templates & builders
│
├── schemas/              # Pydantic schemas
│   ├── block_schema.py   # FrappeBlock, content schemas
│   ├── header_schema.py  # HeaderConfig
│   └── footer_schema.py  # FooterConfig
│
├── design_system/        # Design tokens & themes
│   ├── tokens.py         # Spacing, typography, etc.
│   ├── styles.py         # Base component styles
│   └── themes/           # 6 creative themes
│
├── prompts/              # AI prompts
│   ├── system_prompts.py
│   ├── creative_prompts.py
│   └── anti_patterns.py
│
├── validators/           # Block validation
│   ├── block_validator.py
│   └── auto_fixer.py
│
└── rag/                  # Template retrieval
    └── template_retriever.py
```

## Quick Start

### Basic Page Generation

```python
from builder.ai import PageGenerator, generate_page

# Using convenience function
blocks = generate_page(
    prompt="Create a landing page for a SaaS product",
    theme="modern",
    site_type="saas"
)

# Using generator class
generator = PageGenerator(provider="openai")
blocks = generator.generate_page(
    prompt="Marketing agency website",
    theme="creative",
    site_type="multi_page",
    include_header=True,
    include_footer=True
)
```

### Section Generation

```python
from builder.ai.generators import SectionGenerator

generator = SectionGenerator()
hero_block = generator.generate(
    section_type="hero",
    context="A project management SaaS tool",
    theme="modern"
)
```

### Header/Footer Generation

```python
from builder.ai.generators import HeaderGenerator, FooterGenerator

header_gen = HeaderGenerator()
header = header_gen.generate(
    site_description="E-commerce store",
    site_type="ecommerce",
    pages=["Home", "Products", "Cart", "Account"],
    theme="minimal"
)

footer_gen = FooterGenerator()
footer = footer_gen.generate(
    site_description="Tech startup",
    site_type="saas",
    theme="modern"
)
```

## Configuration

### Site config keys

All AI settings live in `sites/<site>/site_config.json` (pushed by
the operator, e.g. by a fleet provisioning tool). Recognised keys:

- **ai_provider**: `openai` (default) or `ollama`
- **openai_api_key**: Moonshot / OpenAI-compatible API key
- **openai_base_url**: e.g. `https://api.moonshot.ai/v1`
- **openai_model**: e.g. `kimi-k2.5`
- **ollama_base_url** / **ollama_model** / **ollama_api_key**: for local dev
- **ai_temperature**: 0.0-1.0 (default 0.6)
- **ai_max_tokens**, **ai_request_timeout**
- **ai_default_theme**, **ai_default_site_type**, **ai_output_language**

Override locally with `bench --site <site> set-config <key> <value>`.

### Programmatic Configuration

```python
from builder.ai.config import AIConfig, get_ai_settings

# Resolved from site_config.json + hardcoded defaults
config = get_ai_settings()

# Or create custom config
config = AIConfig(
    provider="ollama",
    model="llama3.1:8b",
    temperature=0.7,
)
```

## Themes

Available themes:

| Theme | Description |
|-------|-------------|
| `modern` | Clean, professional with subtle gradients |
| `neobrutalist` | Bold borders, high contrast, playful |
| `glassmorphism` | Frosted glass effects, soft backgrounds |
| `minimal` | Ultra-clean, lots of whitespace |
| `corporate` | Professional, trust-building |
| `creative` | Unique layouts, artistic elements |

```python
from builder.ai.design_system import get_theme, list_themes

# Get theme configuration
theme = get_theme("neobrutalist")
print(theme["colors"])
print(theme["characteristics"])

# List all themes
themes = list_themes()  # ['modern', 'neobrutalist', ...]
```

## Site Types

| Type | Header Features | Typical Sections |
|------|-----------------|------------------|
| `single_page` | Anchor navigation | Hero, Features, CTA |
| `multi_page` | Page navigation | Hero, Features, Stats, CTA |
| `multi_page_auth` | + Login/Signup | Same as multi_page |
| `ecommerce` | Search, Cart, User | Hero, Products, Testimonials |
| `saas` | Product nav, Pricing | Hero, Features, Pricing, FAQ |
| `blog` | Categories, Search | Hero, Categories, Subscribe |
| `portfolio` | Minimal | Hero, Work, Testimonials |

## Content Schemas

The AI generates content using Pydantic schemas:

```python
from builder.ai.schemas.block_schema import (
    HeroContent,
    FeaturesContent,
    PricingContent,
    # ...
)

# AI generates this:
content = HeroContent(
    headline="Build Faster",
    subheadline="Ship products 10x faster",
    primary_cta_text="Start Free",
)

# Templates use it to build blocks
from builder.ai.templates.sections import build_hero_section
block = build_hero_section(content, variant="centered")
```

## Validation

```python
from builder.ai.validators import BlockValidator, AutoFixer, validate_block

# Quick validation
is_valid, report = validate_block(block)

# Detailed validation
validator = BlockValidator()
validator.validate(block)
print(validator.errors)
print(validator.warnings)

# Auto-fix issues
fixer = AutoFixer()
fixed_block = fixer.fix(block)
print(fixer.get_fixes_report())
```

## API Endpoints

The module exposes these Frappe whitelist functions:

| Endpoint | Description |
|----------|-------------|
| `generate_page_blocks` | Generate complete page |
| `generate_section` | Generate single section |
| `generate_header` | Generate header block |
| `generate_footer` | Generate footer block |
| `get_ai_themes` | List available themes |
| `get_ai_site_types` | List site types |
| `check_ai_provider_status` | Check if provider is available |

## Testing

Run tests:

```bash
cd builder
python -m pytest builder/tests/test_ai_*.py -v
```

## Extending

### Adding a New Theme

1. Create `builder/ai/design_system/themes/mytheme.py`:

```python
MYTHEME_THEME = {
    "name": "My Theme",
    "colors": {
        "primary": "#...",
        # ...
    },
    "characteristics": [...],
    "styles": {...},
    "prompt": "...",
}
```

2. Register in `themes/__init__.py`:

```python
from builder.ai.design_system.themes.mytheme import MYTHEME_THEME
THEMES["mytheme"] = MYTHEME_THEME
```

### Adding a New Section Type

1. Add content schema in `schemas/block_schema.py`:

```python
class MyContent(BaseModel):
    title: str
    items: list[str]

SECTION_CONTENT_SCHEMAS["mysection"] = MyContent
```

2. Add template in `templates/sections.py`:

```python
SECTION_TEMPLATES["mysection"] = {
    "description": "My custom section",
    "structure": {...}
}

def build_mysection(content, theme_styles=None):
    # Build block from content
    ...
```

3. Register builder:

```python
def build_section_from_content(section_type, content, theme_styles):
    builders = {
        ...,
        "mysection": lambda c: build_mysection(c, theme_styles),
    }
```

## Best Practices

1. **Always validate output** - Use BlockValidator before using generated blocks
2. **Use appropriate themes** - Match theme to site purpose
3. **Provide context** - Better prompts = better output
4. **Use Ollama for privacy** - Self-hosted, no data leaves your server
5. **Test with different providers** - Ollama and OpenAI may produce different results
