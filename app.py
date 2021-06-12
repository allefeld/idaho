#!/usr/bin/env python3

import os
import webbrowser

from flask import Flask, request
from werkzeug.exceptions import NotFound
from media import Sources


app = Flask(__name__)

sources = Sources.get()

url = f'http://{os.environ["FLASK_RUN_HOST"]}:{os.environ["FLASK_RUN_PORT"]}/'
webbrowser.open(url)


@app.route('/')
def show_main():
    return sources.render()


@app.route('/<path:path>/')
def show_path(path):
    # determine entry that should respond to the request
    entry = sources
    for part in path.split('/'):
        if part not in entry:
            raise NotFound(f'Cannot find "{part}".')
        entry = entry[part]
    # check for arguments
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
                # up. `url/` → `url/?play` → `url/`, so that going back in
                # history does not move before `url/`. Solution: Have a
                # response that triggers going back to the previous page by JS.
    return entry.render()
