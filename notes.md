# TODO

"everything" meta collection

search-based collection


consolidate repetitive HTML by using Jinja functionality
move `render`, `render_tile` functionality to `app.py`?
semanticize HTML:
-   `<div class="header">` → `<header>`
-   `<div class="entries">` → `<main>`

logging, ability to filter log messages

streaming
merge video and subtitles into mkv

music videos? https://imvdb.com/


# Formats

RARBG torrents (`completed`):

-   movie in folder
    name is dotted: title, year, tags
    video file with same name as folder (except for [] at the end)
    one or more subtitles in subfolder `Subs`, name: number `_` language
    → create `Movie`

-   series season in folder
    name is dotted: title, Sxx, tags
    episode files with same name as folder but SxxEyy (and without [])
    subtitles in subfolder `Subs`; it can be complicated
    → create `Season` (later aggregated within `Series`)

processed media (`unseen`, `Movies`, `Series`):

-   movie file
    name: director(s) - title - year
    extensions: avi, mp4, mkv
    subtitle in the same folder with other extension
    → create `Movie`

-   series folder
    name is title
    seasons subfolders `Season x` (miniseries may be directly in series folder)
    containing episodes, naming varies
    → create `Series` containing `Season`s

-   movie collection folder
    contents like movie file, but title - director(s) - year
    → create `Movie`s, but with collection tag, or `Collection`

Playing a movie is opening the file,
playing a season is opening the folder,
both with `xdg-open`.

a file can be:
-   a movie

a folder can be:
-   a torrent movie
-   a torrent season
-   a series → scan as sub-source for seasons
-   a movie collection → scan as sub-source for movie files
    special name to indicate sequence!

The last two need to be disambiguated!
-   maybe by the success of a Series lookup?
-   or by a `folder_probes` parameter to `Source`?

Maybe don't have specifically a movie collection, but a `Source` within a `Source`? That would suggest making `Sources` a special kind of `Source`. There's actually no need for `Sources`, except that its tiles are rendered differently. Okay, also it doesn't have a path and can't be opened.

How would we render movie collection tiles anyway?
