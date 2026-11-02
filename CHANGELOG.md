# Changelog

## v0.4
- "Your posts" is its own section in the GUI, with pagination (15 per page) and photo thumbnails.
- Editing a post shows a "Post URL" field. Leave it alone to keep the address; change it and the old address stops working. Taken addresses get `-2`, `-3`.
- The admin page is split into `admin.html`, `admin.css` and `admin.js`.
- The video field's prompt now lives inside the field.
- Thumbnails are WebP instead of JPEG. Old `.jpg` thumbnails are cleaned up on the next build.

## v0.3
- Fixed the Archive page: text posts no longer stretch over the whole page. Text and video posts are now square label tiles (title, plus 🎥 for video) the same size as photo thumbnails.
- Clearer video field: "Paste a YouTube or Vimeo link, or your own <iframe> code!"
- Pretty URLs: new posts live at `/post/<title-words>/`, taken from the title, else the first few words of the caption, else a hash. Duplicates get `-2`, `-3`. A post's URL never changes after it's created, and posts from earlier versions keep their current URLs.

## v0.2
- Thumbnails (400px square, cached in `content/thumbs/`), via Pillow.
- Archive page at `/archive/`, grouped by month, built from thumbnails.
- Drag-to-reorder (plus arrow buttons) for photo posts; first photo is the cover.
- Video posts now take embed code from any site. Plain YouTube/Vimeo links still work, and v0.1 video posts are converted automatically.
- Version footer in the GUI.

## v0.1
- Text, photo gallery and video posts, posting GUI, Jinja2 themes, tag pages, RSS.
