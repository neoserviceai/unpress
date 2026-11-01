"""The shape of a generated article.

Kept deliberately small. A blog post is mostly prose, and the fields the model
has to fill are the ones a person would have to fill anyway — the rest of Blog
Post (route, author, dates, read time) is derived by the app.
"""

from pydantic import BaseModel, Field


class GeneratedArticle(BaseModel):
	"""One blog post, written for a specific site."""

	title: str = Field(
		...,
		description=(
			"The headline. Specific and concrete — a reader should know what they "
			"get from it. No colons-and-subtitle formula, no clickbait."
		),
	)
	intro: str = Field(
		...,
		description=(
			"One or two sentences shown in the listing and in search results. "
			"Says what the article is about, not that it exists."
		),
	)
	content_md: str = Field(
		...,
		description=(
			"The article in Markdown. Start at '## ' — the H1 is the title and is "
			"rendered by the page, so repeating it here duplicates it. Use short "
			"paragraphs, two to four sections, and lists only where a list is "
			"genuinely the right shape. No image tags: the images are handled "
			"separately."
		),
	)
	meta_description: str = Field(
		default="",
		description="Under 160 characters, for search results. May repeat the intro.",
	)
