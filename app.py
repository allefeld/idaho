#!/usr/bin/env python3

from flask import Flask, request, render_template
from werkzeug.exceptions import NotFound
from jinja2 import environment
from media import Sources


app = Flask(__name__)

sources = Sources.get()


@app.route('/')
def show_main():
    return render_template('sources.html', sources=sources)


@app.route('/<path:path>/')
def show_path(path):
    # determine entry that should respond to the request
    entry = sources
    for part in path.split('/'):
        if part not in entry:
            raise NotFound(f'Cannot find "{part}".')
        entry = entry[part]
    # check for arguments and trigger actions
    if len(request.args) > 0:
        # perform actions in response
        for key, value in request.args.items():
            if key == 'open':
                entry.open()
                return 'opened'
                # triggered by JS `fetch`, response is ignored
            if key == 'refresh':
                entry.refresh()
                return 'refreshed'
                # triggered by JS `fetch`, response is ignored
            if key == 'play':
                entry.play(value)
                return r'<script>window.history.back();</script>'
                # Here we can't use a dummy response and triggering via
                # `fetch`, because then the URL is not entered in the history,
                # so we can't use `a:visited` to mark played items. We could
                # use `flask.redirect`, but then the history would be messed
                # up, `url/` → `url/?play` → `url/`, so that going back in
                # history does not move before `url/`. Solution: Have a
                # response that triggers going back to the previous page by JS.
    # render entry
    type = entry.__class__.__name__
    if type in ['Collection', 'Source']:
        return render_template('collection.html', collection=entry)
    elif type == 'Movie':
        return render_template('movie.html', movie=entry)
    elif type == 'Series':
        return render_template('series.html', series=entry)
    elif type == 'Season':
        return render_template('season.html', season=entry)
    return render_template('unknown.html', unknown=entry)


def genre_id(genre):
    # translate genre string to CSS-safe string
    return genre.translate(str.maketrans('', '', ' &-'))


# register `genre_id` as jinja filter `gid`
app.jinja_env.filters['gid'] = genre_id
