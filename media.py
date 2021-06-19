#!/usr/bin/env python3

import os
import re
import subprocess
from statistics import median

from yaml import unsafe_load, dump, YAMLObject
import tmdbsimple as tmdb

import cfg

# TMDb configuration
tmdb.API_KEY = cfg.TMDb_API_key
search = tmdb.Search()
IMAGE_BASE_URL = 'http://image.tmdb.org/t/p/w185'

# mapping to unify TMDb's movie and TV genres for filter
genre_filter_map = {
    'Adventure':        'Action & Adventure',
    'Fantasy':          'Sci-Fi & Fantasy',
    'Action':           'Action & Adventure',
    'Science Fiction':  'Sci-Fi & Fantasy',
    'War':              'War & Politics',
}


class Entry(YAMLObject):
    def open(self):
        # open (containing) folder
        path = self.path
        if os.path.isfile(path):
            path = os.path.dirname(path)
        print('opening', self)
        subprocess.Popen(['xdg-open', path])

    def refresh(self):
        print('refreshing', self)
        # invalidate info
        if hasattr(self, 'info'):
            self.info = None
        # recreate info
        self.add_info()
        # save updated data
        Sources.get().save_all()

    def date(self):
        return '?'

    def type(self):
        return self.__class__.__name__

    def __repr__(self):
        return f'Entry(path="{self.path}")'


class Entries:
    def __iter__(self):
        return iter(self.entries.keys())

    def __getitem__(self, key):
        return self.entries[key]


class Unknown(Entry):
    yaml_tag = '!Unknown'

    def __init__(self, path):
        self.path = path

    def add_info(self):
        pass

    def filter_genres(self):
        return {}

    def __repr__(self):
        return f'Unknown(path="{self.path}")'


class Movie(Entry):
    yaml_tag = '!Movie'

    def __init__(self, tmbd_id, path):
        self.tmdb_id = tmbd_id
        self.path = path
        self.info = None

    def add_info(self):
        # create uid and use it to check whether `info` is up-to-date
        uid = f'M{self.tmdb_id}'
        if (self.info is not None) and (self.info['uid'] == uid):
            return
        # if not, get information from TMDb
        movie = tmdb.Movies(self.tmdb_id)
        movie.info()
        movie.credits()
        # augmented genres
        genres = [genre['name'] for genre in movie.genres]
        if movie.adult:
            genres.append('Adult')
        # add `info`
        self.info = {
            'uid':          uid,
            'date':         movie.release_date,
            'title':        movie.original_title,
            'title_en':     (movie.title if movie.title != movie.original_title
                             else None),
            'year':         movie.release_date[:4],
            'directors':    ', '.join(person['name'] for person in movie.crew
                                      if person['job'] == 'Director'),
            'writers':      ', '.join(person['name'] for person in movie.crew
                                      if person['job']
                                      in ['Writer', 'Screenplay']),
            'actors':       ', '.join(person['name'] for person in movie.cast
                                      if person['order'] < 3),
            'genres':       genres,
            'runtime':      movie.runtime,
            'countries':    '/'.join(country['iso_3166_1'] for country
                                     in movie.production_countries),
            'poster_url':   IMAGE_BASE_URL + movie.poster_path,
            'imdb_id':      movie.external_ids()['imdb_id'],
            'vote_average': movie.vote_average
        }

    def date(self):
        return self.info['date']

    def filter_genres(self):
        return {genre_filter_map.get(genre, genre)
                for genre in self.info['genres']}

    def play(self, _):
        if os.path.isfile(self.path):
            mpv_play(self.path)
            return
        if os.path.isdir(self.path):
            # folder path
            # look for largest file, and collect subfolders
            filename = None
            subs = []
            size = 0
            for n in os.listdir(self.path):
                fn = os.path.join(self.path, n)
                if os.path.isfile(fn):
                    s = os.path.getsize(fn)
                    print('FILE', s, '\t', fn)
                    if s > size:
                        size = s
                        filename = fn
                if os.path.isdir(fn):
                    print('DIR', fn)
                    subs.append(n)
            if filename is not None:
                mpv_play(filename, sub_auto_all=True, subs=subs)
                return

    def __repr__(self):
        return f'Movie(tmdb_id={self.tmdb_id}, path="{self.path}")'


class Season(Entry):
    yaml_tag = '!Season'

    def __init__(self, tmbd_id, season_number, path):
        self.tmdb_id = tmbd_id
        self.season_number = season_number
        self.path = path
        self.info = None
        self.episodes = []

    def add_info(self):
        # scan for episodes
        self.episodes = scan_episodes(self.path, self.season_number)
        # create uid and use it to check whether `info` is up-to-date
        uid = f'S{self.tmdb_id}s{self.season_number}'
        if (self.info is not None) and (self.info['uid'] == uid):
            return
        # if not, get information from TMDb
        series, seasons = get_series_info(self.tmdb_id)
        season = None
        for s in seasons:
            if s['season_number'] == self.season_number:
                season = s
                break
        if (season is not None) and (season['poster_path'] is not None):
            poster_url = IMAGE_BASE_URL + season['poster_path']
        else:
            poster_url = series['poster_url']
        if season is not None:
            date = season['air_date']
            year = date[:4]
        else:
            # assume that there's one season per year
            dp = series['date'].split('-')
            dp[0] = str(int(dp[0]) + self.season_number - 1)
            date = '-'.join(dp)
            year = date[:4] + ' ?'
        # add `info`
        self.info = {
            'uid':        uid,
            'date':       date,
            'name':       (season['name'] if season is not None
                           else f'Season {self.season_number}'),
            'poster_url': IMAGE_BASE_URL + poster_url,
            'year':       year,
            'series':     series
        }

    def date(self):
        return self.info['date']

    def filter_genres(self):
        return {genre_filter_map.get(genre, genre)
                for genre in self.info['series']['genres']}

    def play(self, episode_index):
        episode_index = int(episode_index)
        filename = os.path.join(self.path, self.episodes[episode_index][1])
        mpv_play(filename)
        return

    def __getstate__(self):
        # prevent `episodes` from being stored
        state = self.__dict__.copy()
        del state['episodes']
        return state

    def __repr__(self):
        return (f'Season(tmdb_id={self.tmdb_id}, '
                + f'season_number={self.season_number}, '
                + f'path="{self.path}")')


def get_series_info(tmdb_id):
    # used by `Series.add_info()` and `Season.add_info()`
    series = tmdb.TV(tmdb_id)
    series.info()
    series.credits()

    first_year = series.first_air_date[:4]
    last_year = series.last_air_date[:4]
    if last_year == first_year:
        years = first_year
    else:
        years = f'{first_year}–{last_year}'

    info = {
        'date':              series.first_air_date,
        'name':              series.original_name,
        'name_en':           (series.name
                              if series.name != series.original_name
                              else None),
        'years':             years,
        'number_of_seasons': series.number_of_seasons,
        'creators':          ', '.join(person['name']
                                       for person in series.created_by),
        'actors':            ', '.join(person['name'] for person in series.cast
                                       if person['order'] < 3),
        'genres':            [genre['name'] for genre in series.genres],
        'countries':         '/'.join(country['iso_3166_1'] for country
                                      in series.production_countries),
        'runtime':           (median(series.episode_run_time)
                              if len(series.episode_run_time) > 0 else '?'),
        'poster_url':        IMAGE_BASE_URL + series.poster_path,
        'imdb_id':           series.external_ids()['imdb_id'],
        'vote_average':      series.vote_average
    }
    return info, series.seasons


class Series(Entry, Entries):
    yaml_tag = '!Series'

    def __init__(self, tmbd_id, path):
        self.tmdb_id = tmbd_id
        self.path = path
        self.info = None
        self.entries = dict()
        self.episodes = []

    def add_info(self):
        # separate entries into seasons and movies
        seasons = {name: entry for name, entry in self.entries.items()
                   if isinstance(entry, Season)}
        movies = {name: entry for name, entry in self.entries.items()
                  if isinstance(entry, Movie)}
        # scan for seasons
        seasons = scan_folder(
            self.path, seasons,
            [lambda name, path:
                probe_processed_folder_season(name, path, self.tmdb_id)],
            [])
        if len(seasons) > 0:
            # if there are seasons, scan for movies
            movies = scan_folder(
                self.path, movies,
                [],
                [probe_processed_file_movie])
            # put seasons and movies together as entries, sorted
            entries = seasons
            entries.update(movies)
            entries = dict(sorted(entries.items(),
                                  key=lambda item: item[1].date()))
            self.entries = entries
            # no episodes
            self.episodes = []
        else:
            # if there are no seasons (Miniseries), scan for episodes
            self.episodes = scan_episodes(self.path, 1)
            # no seasons and movies
            self.entries = dict()
        # create uid and use it to check whether `info` is up-to-date
        uid = f'S{self.tmdb_id}'
        if (self.info is not None) and (self.info['uid'] == uid):
            return
        # if not, get information from TMDb
        self.info, _ = get_series_info(self.tmdb_id)
        self.info['uid'] = uid

    def date(self):
        return self.info['date']

    def filter_genres(self):
        return {genre_filter_map.get(genre, genre)
                for genre in self.info['genres']}

    def play(self, episode_index):
        episode_index = int(episode_index)
        filename = os.path.join(self.path, self.episodes[episode_index][1])
        mpv_play(filename)
        return

    def __getstate__(self):
        # prevent `episodes` from being stored
        state = self.__dict__.copy()
        del state['episodes']
        return state

    def __repr__(self):
        return (f'Series(tmdb_id={self.tmdb_id}, path="{self.path}")')


class Collection(Entry, Entries):
    yaml_tag = '!Collection'

    def __init__(self, path, title):
        self.path = path
        self.title = title
        self.entries = dict()

    def add_info(self):
        # scan folder for entries
        folder_probes = [probe_torrent_folder_season,
                         probe_torrent_folder_movie,
                         probe_processed_folder_series,
                         probe_processed_folder_collection]
        file_probes = [probe_processed_file_movie]
        self.entries = scan_folder(self.path, self.entries,
                                   folder_probes, file_probes)

    def date(self):
        if len(self.entries) > 0:
            # date from first entry
            return list(self.entries.values())[0].info['date']
        else:
            return '?'

    def filter_genres(self):
        fg = set()
        for entry in self.entries.values():
            fg.update(entry.filter_genres())
        return fg

    def __repr__(self):
        return f'Collection(path="{self.path}", title="{self.title}")'


class Source(Collection):
    # a `Source` is a `Collection` that is backed by a YAML-format cache

    def __init__(self, path, title):
        super().__init__(path, title)
        print('initializing', self)
        self.load()
        self.add_info()
        self.save()

    def load(self):
        # determine name of entries file
        entries_file = os.path.join(self.path, '.idaho.yaml')
        # load entries from YAML file if it exists
        try:
            with open(entries_file, 'r') as f:
                self.entries = unsafe_load(f)
            print('  loaded entries file')
        except FileNotFoundError:
            print('  no entries file')

    def save(self):
        # determine name of entries file
        entries_file = os.path.join(self.path, '.idaho.yaml')
        # make backup if file exists
        if os.path.exists(entries_file):
            os.rename(entries_file, entries_file + '.bk')
        # dump entries to YAML file
        with open(entries_file, 'w') as f:
            dump(self.entries, f, default_flow_style=False, sort_keys=False)
        print('  saved entries file')

    def __repr__(self):
        return f'Source(path="{self.path}", title="{self.title}")'


class Sources(Entries):

    sources = None

    @classmethod
    def get(cls):
        # get singleton instance
        if cls.sources is None:
            cls.sources = Sources()
        return cls.sources

    def __init__(self):
        # create `Source` entries from configuration
        entries = dict()
        for name, source_folder in cfg.sources.items():
            entries[name] = Source(source_folder, name)

        # store entries
        self.entries = entries

    def save_all(self):
        # save all sources
        for name in self.entries:
            self.entries[name].save()
        print('saved entries files')

    def __repr__(self):
        return 'Sources()'


# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––


def scan_episodes(path, season_number):
    # get folder contents
    names = os.listdir(path)
    # filter out hidden
    names = [name for name in names if not name.startswith('.')]
    # filter for video files
    names = [name for name in names
             if os.path.isfile(os.path.join(path, name))
             and (os.path.splitext(name)[1] in cfg.video_extensions)]
    # extract episode numbers
    pattern = r'(?i)S(\d{1,2}) ?E(\d{1,2})(?:(?:-E|E|,)(\d{1,2}))?'
    episodes = []
    for name in names:
        episode = os.path.splitext(name)[0]
        match = re.search(pattern, name)
        if match and int(match.group(1)) == season_number:
            episode = f'Episode {int(match.group(2)):2}'
            if match.group(3) is not None:
                episode += f'–{int(match.group(3))}'
        episodes.append((episode, name))
    # sort episodes
    episodes = sorted(episodes, key=lambda item: item[0])
    return episodes


def probe_processed_folder_season(name, path, tmdb_id):
    print(f'    probing "{name}" as processed_folder_season')
    # check pattern: Season, #
    pattern = r'Season ([0-9]+)'
    match = re.fullmatch(pattern, name)
    if not match:
        return None
    season_number = int(match.group(1))
    # return entry
    return Season(tmdb_id, season_number, os.path.join(path, name))


def probe_processed_folder_collection(name, path):
    print(f'    probing "{name}" as processed_folder_collection')
    # check pattern: ... collection
    pattern = r'(.+) collection'
    match = re.fullmatch(pattern, name)
    if not match:
        return None
    title = match.group(1)
    # return entry
    return Collection(os.path.join(path, name), title)


def probe_torrent_folder_movie(name, path):
    print(f'    probing "{name}" as torrent_folder_movie')
    # check pattern: title, year, extra; separated by dots
    pattern = r'(.*)\.([1-3][0-9]{3})\.(.*)'
    match = re.fullmatch(pattern, name)
    if not match:
        return None
    title = match.group(1)
    title = ' '.join(title.split('.'))
    year = int(match.group(2))
    # extra = match.group(3)
    # extra = ' '.join(extra.split('.'))
    # look movie up
    response = search.movie(query=title, year=year, include_adult=True)
    results = response['results']
    if len(results) == 0:
        return None
    result = results[0]
    for r in results:
        if r['title'] == title:
            result = r
            break
    # return entry
    return Movie(result['id'], os.path.join(path, name))


def probe_torrent_folder_season(name, path):
    print(f'    probing "{name}" as torrent_folder_season')
    # check pattern: title, S#, extra; separated by dots
    pattern = r'(.*)\.S([0-9]{2})\.(.*)'
    match = re.fullmatch(pattern, name)
    if not match:
        return None
    title = match.group(1)
    title = ' '.join(title.split('.'))
    season_number = int(match.group(2))
    # extra = match.group(3)
    # extra = ' '.join(extra.split('.'))
    # look series up
    response = search.tv(query=title, include_adult=True)
    results = response['results']
    if len(results) == 0:
        # Sometimes, there's a year part before the S# part, which stumps TMDb.
        # If there were no results, and the last part looks like a year, remove
        # it from the title and try again.
        # We can't always remove it, because it might be part of the title.
        ts = title.split(' ')
        pattern = '[1-3][0-9]{3}'
        if (len(ts) > 1) and re.fullmatch(pattern, ts[-1]):
            title = ' '.join(ts[:-1])
            response = search.tv(query=title, include_adult=True)
            results = response['results']
    if len(results) == 0:
        return None
    result = results[0]
    for r in results:
        if r['name'] == name:
            result = r
            break
    # return entry
    return Season(result['id'], season_number, os.path.join(path, name))


def probe_processed_file_movie(name, path):
    print(f'    probing "{name}" as processed_file_movie')
    # check pattern: director(s) - title (extra) - year
    pattern = r'.* - ([^\(]*) (?:\((.*)\) )?- ([1-3][0-9]{3})\..*'
    match = re.fullmatch(pattern, name)
    if not match:
        return None
    title = match.group(1)
    # extra = match.group(2)
    # if extra is None:
    #     extra = ''
    year = int(match.group(3))
    # look movie up
    response = search.movie(query=title, year=year, include_adult=True)
    results = response['results']
    if len(results) == 0:
        return None
    result = results[0]
    for r in results:
        if r['title'] == title:
            result = r
            break
    # return entry
    return Movie(result['id'], os.path.join(path, name))


def probe_processed_folder_series(name, path):
    print(f'    probing "{name}" as processed_folder_series')
    # look series up
    response = search.tv(query=name, include_adult=True)
    results = response['results']
    if len(results) == 0:
        return None
    result = results[0]
    for r in results:
        if r['name'] == name:
            result = r
            break
    # return entry
    return Series(result['id'], os.path.join(path, name))


def scan_folder(path, old_entries, folder_probes, file_probes):
    print(f'  scanning "{path}"')
    # get file & folder names
    names = os.listdir(path)
    # filter out hidden
    names = [name for name in names if not name.startswith('.')]
    # filter out non-video files (keep folders)
    names = [name for name in names
             if os.path.isdir(os.path.join(path, name))
             or (os.path.splitext(name)[1] in cfg.video_extensions)]
    # filter out names for which there are no probes
    if len(folder_probes) == 0:
        names = [name for name in names
                 if not os.path.isdir(os.path.join(path, name))]
    if len(file_probes) == 0:
        names = [name for name in names
                 if not os.path.isfile(os.path.join(path, name))]

    # update entry names
    entries = {name: old_entries.get(name, None) for name in names}
    removed = list(set(old_entries) - set(entries))
    for name in removed:
        print('    removed', old_entries[name])

    # create new entries
    for name, entry in entries.items():
        if entry is None:
            if os.path.isdir(os.path.join(path, name)):
                # folder
                for probe in folder_probes:
                    if entry is None:
                        entry = probe(name, path)
            else:
                # file
                for probe in file_probes:
                    if entry is None:
                        entry = probe(name, path)
            if entry is None:
                print('      *** unable to identify')
                entry = Unknown(os.path.join(path, name))
            print('      added', entry)
            entries[name] = entry

    # update entry information
    for name, entry in entries.items():
        if entry is not None:
            print('  adding info to', entry)
            entry.add_info()

    # sort entries
    entries = dict(sorted(entries.items(),
                          key=lambda item: item[1].date()))

    return entries


def mpv_play(filename, sub_auto_all=False, subs=[]):
    cmd = ['mpv', '--fs', '--save-position-on-quit']
    if sub_auto_all:
        cmd.append('--sub-auto=all')
    if len(subs) > 0:
        cmd.append('--sub-file-paths=' + ':'.join(subs))
    cmd.append(filename)
    print('executing', ' '.join(cmd))
    subprocess.Popen(cmd)
