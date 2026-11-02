"""Storage + site builder. Posts are plain JSON files; the site is plain HTML."""
import html, json, re, shutil, time, unicodedata, uuid
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

try:
    from PIL import Image, ImageOps
except ImportError:  # thumbnails are skipped (originals used) if Pillow is missing
    Image = None

ROOT = Path(__file__).resolve().parent.parent
DATA, SITE, THEMES = ROOT / "content", ROOT / "site", ROOT / "themes"
POSTS, MEDIA, THUMBS = DATA / "posts", DATA / "media", DATA / "thumbs"
THUMB_SIZE = 400
TYPES = ("text", "image", "video")
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg"}
DEFAULTS = {"title": "My Spoke Blog", "description": "Notes from the saddle.",
            "author": "", "posts_per_page": 10, "theme": "cruiser", "base_url": ""}


def ensure():
    POSTS.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)


# ---------- config & posts ----------
def load_config():
    cfg = dict(DEFAULTS)
    p = DATA / "config.json"
    if p.exists():
        cfg.update(json.loads(p.read_text("utf-8")))
    return cfg


def save_config(new):
    cfg = load_config()
    for k in DEFAULTS:
        if k in new:
            cfg[k] = new[k]
    cfg["posts_per_page"] = max(1, int(cfg["posts_per_page"] or 10))
    cfg["base_url"] = str(cfg["base_url"]).strip().rstrip("/")
    ensure()
    (DATA / "config.json").write_text(json.dumps(cfg, indent=2), "utf-8")
    return cfg


def list_themes():
    return sorted(p.name for p in THEMES.iterdir() if (p / "layout.html").exists())


def load_posts():
    ensure()
    posts = [migrate(json.loads(f.read_text("utf-8"))) for f in POSTS.glob("*.json")]
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def page_posts(page=1, per=15):
    posts = load_posts()
    pages = max(1, -(-len(posts) // per))
    page = min(max(1, page), pages)
    return {"posts": posts[(page - 1) * per:page * per], "total": len(posts), "page": page, "pages": pages}


def save_post(data, pid=None):
    ensure()
    old = {}
    if pid:
        f = POSTS / f"{pid}.json"
        if not f.exists():
            raise ValueError("No such post")
        old = json.loads(f.read_text("utf-8"))
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = tags.split(",")
    ptype = data.get("type", "text")
    if ptype not in TYPES:
        raise ValueError("Unknown post type")
    post = {
        "id": pid or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4],
        "type": ptype,
        "title": str(data.get("title", "")).strip(),
        "body": str(data.get("body", "")).strip(),
        "tags": [t.strip().lstrip("#") for t in tags if t.strip().lstrip("#")],
        "images": [{"file": Path(str(i["file"])).name} for i in data.get("images", [])] if ptype == "image" else [],
        "embed_code": clean_embed(data.get("embed_code", "")) if ptype == "video" else "",
        "date": old.get("date") or data.get("date") or datetime.now().isoformat(timespec="seconds"),
    }
    if pid:  # slugs stay put on edit unless a new one is typed into the URL field
        wanted = slugify(str(data.get("slug", "")), 100)
        post["slug"] = unique_slug(wanted, pid) if wanted else (old.get("slug") or pid)
    else:
        post["slug"] = make_slug(post)
    (POSTS / f"{post['id']}.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), "utf-8")
    return post


def delete_post(pid):
    (POSTS / f"{Path(pid).name}.json").unlink(missing_ok=True)


def save_upload(filename, raw):
    ensure()
    p = Path(filename)
    ext = p.suffix.lower()
    if ext not in IMG_EXT:
        raise ValueError("Unsupported image type")
    stem = re.sub(r"[^\w-]+", "-", p.stem).strip("-")[:40] or "image"
    name = f"{stem}-{uuid.uuid4().hex[:6]}{ext}"
    (MEDIA / name).write_bytes(raw)
    make_thumb(name)
    return name


# ---------- thumbnails ----------
def make_thumb(name):
    """Square-crop WebP thumbnail cached in content/thumbs. Returns its filename, or None."""
    src = MEDIA / name
    dst = THUMBS / (Path(name).stem + ".webp")
    if Image is None or src.suffix.lower() == ".svg" or not src.exists():
        return None
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst.name
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            im = im.convert("RGBA" if "A" in im.getbands() or "transparency" in im.info else "RGB")
            ImageOps.fit(im, (THUMB_SIZE, THUMB_SIZE), Image.LANCZOS).save(dst, "WEBP", quality=80, method=6)
        return dst.name
    except Exception:
        return None


def prune_thumbs():
    """Drop thumbnails with no matching photo, plus the old .jpg ones from earlier versions."""
    keep = {Path(f.name).stem + ".webp" for f in MEDIA.iterdir()}
    for f in THUMBS.iterdir():
        if f.name not in keep:
            f.unlink(missing_ok=True)


# ---------- embeds ----------
def clean_embed(s):
    """Embed code is stored as pasted. A bare video URL is converted for convenience."""
    s = str(s).strip()
    if s and "<" not in s:
        u = embed_url(s) if s.startswith("http") else None
        if u:
            return f'<iframe src="{u}" width="560" height="315" allowfullscreen></iframe>'
        return f'<a href="{html.escape(s)}">{html.escape(s)}</a>' if s.startswith("http") else html.escape(s)
    return s


def embed_info(code):
    """Returns (html, aspect_ratio). Ratio is set only when the iframe has numeric width and height."""
    if not code:
        return "", None
    m = re.search(r"<iframe\b[^>]*>", code, re.I)
    if not m:
        return code, None
    def attr(n):
        a = re.search(rf'[\s"\']{n}\s*=\s*["\']?(\d+)["\']?(?=[\s>/"\'])', m.group(0), re.I)
        return a.group(1) if a else None
    w, h = attr("width"), attr("height")
    return code, (f"{w} / {h}" if w and h else None)


def migrate(p):
    """Posts from v0.1 stored a video_url; turn it into embed code."""
    if p.get("video_url") and not p.get("embed_code"):
        p["embed_code"] = clean_embed(p["video_url"])
    p.pop("video_url", None)
    p.setdefault("embed_code", "")
    p.setdefault("slug", p["id"])  # older posts keep their existing (hash) URL
    return p


def excerpt(text, n=110):
    s = re.sub(r"\]\(https?://[^)]*\)|[*\[\]]", "", text or "")
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n].rstrip() + "…"


RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def slugify(src, limit=60):
    src = "".join(c for c in unicodedata.normalize("NFKD", src) if not unicodedata.combining(c))
    s = re.sub(r"[^\w]+", "-", src.lower()).strip("-")
    if len(s) > limit:
        s = s[:limit].rsplit("-", 1)[0] or s[:limit]
    return s + "-post" if s in RESERVED else s  # Windows can't have folders with these names


def unique_slug(s, exclude_id=None):
    taken = {p["slug"] for p in load_posts() if p["id"] != exclude_id}
    base, n = s, 2
    while s in taken:
        s, n = f"{base}-{n}", n + 1
    return s


def make_slug(post):
    """URL piece from the title, else the first few words of the caption, else the id (hash)."""
    src = post["title"] or " ".join(re.sub(r"https?://\S+", "", excerpt(post["body"], 200)).split()[:6])
    s = slugify(src)
    return unique_slug(s) if s else post["id"]


# ---------- formatting helpers ----------
def fmt(text):
    """Tiny markdown: **bold**, *italic*, [link](url), bare URLs, paragraphs."""
    t = html.escape(text or "", quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r'(?<!["=>])(https?://[^\s<]+)', r'<a href="\1">\1</a>', t)
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    return "".join("<p>" + p.replace("\n", "<br>") + "</p>" for p in paras)


def embed_url(url):
    p = urlparse(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    vid = None
    if host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        if p.path == "/watch":
            vid = parse_qs(p.query).get("v", [""])[0]
        elif p.path.startswith(("/shorts/", "/embed/", "/live/")):
            vid = p.path.split("/")[2] if p.path.count("/") >= 2 else None
    elif host == "youtu.be":
        vid = p.path[1:]
    if vid and re.fullmatch(r"[\w-]+", vid):
        return f"https://www.youtube.com/embed/{vid}"
    m = re.match(r"/(?:.*/)?(\d+)$", p.path)
    if host in ("vimeo.com", "player.vimeo.com") and m:
        return f"https://player.vimeo.com/video/{m.group(1)}"
    return None


def slug(s):
    return re.sub(r"[^\w]+", "-", s.lower()).strip("-") or "tag"


def pretty(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


# ---------- builder ----------
def build():
    ensure()
    prune_thumbs()
    cfg = load_config()
    theme = THEMES / cfg["theme"]
    if not (theme / "layout.html").exists():
        raise ValueError(f"Theme '{cfg['theme']}' not found in themes/")
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    shutil.copytree(MEDIA, SITE / "media")
    if (theme / "static").exists():
        shutil.copytree(theme / "static", SITE / "static")

    env = Environment(loader=FileSystemLoader(theme), autoescape=select_autoescape(["html"]))
    env.filters["fmt"] = lambda s: Markup(fmt(s))

    (SITE / "thumbs").mkdir()
    posts = load_posts()
    for p in posts:
        p["path"] = f"post/{p['slug']}/"
        p["date_pretty"] = pretty(p["date"])
        p["embed_html"], p["embed_ratio"] = embed_info(p["embed_code"])
        for i in p["images"]:
            t = make_thumb(i["file"])
            if t:
                shutil.copy(THUMBS / t, SITE / "thumbs" / t)
            i["thumb"] = f"thumbs/{t}" if t else f"media/{i['file']}"
        p["cover"] = p["images"][0]["thumb"] if p["images"] else None
        p["excerpt"] = excerpt(p["body"])
        p["tag_list"] = [{"name": t, "path": f"tag/{slug(t)}/"} for t in p["tags"]]

    tag_counts = {}
    for p in posts:
        for t in p["tags"]:
            tag_counts.setdefault(slug(t), [t, 0])[1] += 1
    all_tags = sorted(({"name": n, "path": f"tag/{s}/", "count": c} for s, (n, c) in tag_counts.items()),
                      key=lambda t: t["name"].lower())

    def render(template, outdir, **ctx):
        outdir = outdir.strip("/")
        root = "/".join([".."] * len(outdir.split("/"))) if outdir else "."
        out = SITE / outdir / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(env.get_template(template).render(site=cfg, root=root, tags=all_tags, **ctx), "utf-8")

    def paginate(base, items, heading=""):
        per = cfg["posts_per_page"]
        pages = max(1, -(-len(items) // per))
        loc = lambda n: base + ("" if n == 1 else f"page/{n}/")
        for n in range(1, pages + 1):
            render("index.html", loc(n), posts=items[(n - 1) * per:n * per], heading=heading,
                   page=n, pages=pages, prev=loc(n - 1) if n > 1 else None, next=loc(n + 1) if n < pages else None)

    paginate("", posts)
    if (theme / "archive.html").exists():
        months = []
        for p in posts:
            label = datetime.fromisoformat(p["date"]).strftime("%B %Y")
            if not months or months[-1]["label"] != label:
                months.append({"label": label, "posts": []})
            months[-1]["posts"].append(p)
        render("archive.html", "archive", months=months)
    for s, (name, _) in tag_counts.items():
        paginate(f"tag/{s}/", [p for p in posts if any(slug(t) == s for t in p["tags"])], heading=f"#{name}")
    for p in posts:
        render("post.html", p["path"], post=p)

    if cfg["base_url"]:
        base = cfg["base_url"]
        items = ""
        for p in posts[:20]:
            body = "".join(f'<img src="{base}/media/{i["file"]}">' for i in p["images"]) + p["embed_html"] + fmt(p["body"])
            items += (f"<item><title>{html.escape(p['title'] or p['date_pretty'])}</title>"
                      f"<link>{base}/{p['path']}</link><guid>{base}/{p['path']}</guid>"
                      f"<pubDate>{format_datetime(datetime.fromisoformat(p['date']).astimezone())}</pubDate>"
                      f"<description>{html.escape(body)}</description></item>")
        (SITE / "feed.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f"<title>{html.escape(cfg['title'])}</title><link>{base}/</link>"
            f"<description>{html.escape(cfg['description'])}</description>{items}</channel></rss>", "utf-8")
    return len(posts)
