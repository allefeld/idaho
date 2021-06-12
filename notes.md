# TODO

filtering:
-   filter / search. genres, directors, ... maybe Genre + fulltext, info in page but hidden
-   filtering should really be done by CSS, not patching element styles
optimally in a completely generic way; selection element directly carries classes of elements to be hidden

consolidate repetitive HTML by using Jinja functionality
move `render`, `render_tile` functionality to `app.py`?
semanticize HTML:
-   `<div class="header">` → `<header>`
-   `<div class="entries">` → `<main>`

logging, ability to filter log messages

streaming
merge video and subtitles into mkv


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


# Object classes in module `media`

## superclasses

-   `Entry`:
    subclasses: `Movie`, `Series`, `Season`
    & `Franchise`?

-   `Collection`:
    subclasses: `Sources`, `Source`, `Series`
    & `Franchise`?


## rethinking the structure

-   `Sources`, `Source`, `Movie`, `Series`, `Season`
    `render()`
    → ?

-   `Sources`, `Source`, `Series`
    `entries`
    → `Collection`

-   `Movie`, `Series`, `Season`, *and* `Source`
    `path`, `open()`, `render_tile()`
    → `Entry`?

-   `Movie`, `Series`, `Season`
    `tmdb_id`, `path`, `extra`, `info`, `add_info()`
    → ?

What is actually the rationale for these abstractions?
-   inheritance:
    generic `open()` method of `Entry`, assumes presence of `path`
    -   We could have generic `render()` and `render_tile()` methods I guess, but that would still only justify `Entry` (maybe also `Renderable`), and make the templates actually *less* semantic.
    -   The commonalities of `Movie`, `Series`, `Season` cannot be made generic.
    -   `Collection` however could be a container for the now orphaned functions `scan_folder` and `prepare_entries`.
        What to do with `probe_`* though? Well, they could be class methods of `Collection`. And then `probe_season_processed_folder` could be a method of that, too. However, it accesses `self.tmdb`, which is not a general attribute of a collection. Keep it in `Series` then? – Actually we should wait and see how scanning for episodes fits in.
-   ensure the presence of attributes (define an interface)?
    But we never use that, and it could just as well be done via `hasattr`.
    Okay, `isinstance` can indicate the presence of a *set* of attributes.
-   explicit semantics (document an interface).

Is `Source` an `Entry`?
If the definition is being in the `entries` field of a `Collection`, then yes.
But `Sources` works differently, is not a regular `Collection`.
It is designed to hold only `Source`s, and `Source`s should only be in `Sources`.
