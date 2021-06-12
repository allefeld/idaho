import os
from yaml import safe_load

# configuration directory
dir = os.path.join(
    os.environ.get(
        'XDG_CONFIG_HOME',
        os.path.join(
            os.environ.get('HOME'),
            '.config')
        ),
    'idaho')

# load configuration file and add contents to module
with open(os.path.join(dir, 'config.yaml'), 'r') as f:
    globals().update(safe_load(f))
