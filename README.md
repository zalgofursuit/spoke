# Spoke

A tiny static site generator with a social-media-style posting GUI. Text, photo galleries, and video embeds, rendered through Jinja2 themes.

## AI Disclaimer
Yes, this thing was written by Claude. I didn't see anyone else making the tool I specifically wanted. If someone wants to de-sloppify it, I'll be happy to quit prompting and use yours!

## Run it
1. Install Python 3.9+ (python.org). Jinja2 and Pillow (for thumbnails) install themselves on first run.
2. `python run.py` (Windows: `py run.py`). Your browser opens the posting GUI.

Every post or edit rebuilds the site into `site/`. Upload the contents of `site/` to any static host (GitHub Pages, Netlify, Neocities, S3). Pages use relative links, so they also work from a subfolder or when opened from disk.

## URLs
New posts get a readable address from their title (or the first few words of the caption), e.g. `post/gravel-day-at-the-lake/`. With neither, they get a timestamp-and-hash address. The address is set when the post is created and doesn't change when you edit the post. To change it deliberately, open the post for editing and use the Post URL field (old links to it will stop working).

## Layout
- `content/posts/*.json`: your posts. `content/media/`: your images. `content/config.json`: settings. Back up `content/` and you've backed up everything.
- `themes/<name>/`: templates. Pick the theme in Settings.

## Making a theme
Copy `themes/cruiser/`. Required: `layout.html`, `index.html`, `post.html`. Files in `static/` are copied to `site/static/`. Always prefix URLs with `{{ root }}/` so links work at any depth.

| Variable | Available in | Notes |
|---|---|---|
| `site` | all | `title`, `description`, `author`, `base_url`, ... |
| `root` | all | relative path back to the site root |
| `tags` | all | list of `{name, path, count}` |
| `posts`, `page`, `pages`, `prev`, `next`, `heading` | index.html | `prev`/`next` are root-relative paths or none |
| `post` | post.html | see below |

A post has `id`, `type` (`text`/`image`/`video`), `title`, `body`, `images` (each `{file, thumb}`; use `{{ root }}/media/{{ img.file }}` for the original and `{{ root }}/{{ img.thumb }}` for the 400px square WebP thumbnail), `cover` (first image's thumbnail path or none), `excerpt` (plain-text snippet), `embed_html` (video embed code, output with `|safe`), `embed_ratio` (e.g. `560 / 315` when the iframe has numeric width and height, else none), `date`, `date_pretty`, `path`, `tag_list`. Filter `{{ post.body|fmt }}` renders the body (bold, italic, links, paragraphs).

If a theme has an `archive.html`, it's rendered at `/archive/` with `months` (a list of `{label, posts}`, newest first). Embed code is inserted exactly as pasted, so only paste code you trust.
