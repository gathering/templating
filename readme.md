# Templating Service

This is a new version of our templating engine!

Originally developed by [@KristianLyng](https://github.com/KristianLyng), later slightly rewritten by [@Foxboron](https://github.com/Foxboron).

Old source can still be found here: [gondul/templating](https://github.com/gathering/gondul/commits/master/templating/templating.py)

## Caveats

There's one weird thing. To be a bit backwards compatible the last two items of a path will be used as the objects name.

This however opens up for possible name collisions from files and http api data.

Example:

```yaml
---
get:
  - file:///root/templating/data/read/networks.yaml
  - file:///root/templating/data/read/networks.json
  - https://<USER:PW>@gondul.tg23.gathering.org/api/read/networks
  - http://<USER:PW>@gondul.tg23.gathering.org/api/read/networks
```

All of these would be added as `read/networks` in the python dicts. Aka, the last one is going to win.
Therefor, think twice when naming things :)

This is inteded behaviour to support as of now. Helps us run templating offline.

## Features

- Fully async
- Loads data from local files
  - yaml
  - json
- Loads data from API's
- Run a template once with HTTP options

## Currently supported URI locations

- `file://`
  - Can be both a file, or a folder
  - We will attempt to load all files found recursively
  - Can be relative path
- `https://` and `http://`
  - Gets data from API endpoint
  - Supports adding header options (tbh, i just **kwargs this directly to aiohttp..)

## Example file

```yaml
---
get:
  - file:///root/templating/data
  # Relative Path is also supported
  - file://./templating/data
  - https://<USER:PW>@gondul.tg23.gathering.org/api/read/networks
  - http://gondul.tg23.gathering.org/api/public/switches
 - 'https://netbox.tg23.gathering.org/api/ipam/ip-addresses?exclude=config_context&format=json&limit=0':
      headers:
        Authorization: 'Token <TOKEN>'
```

## Example Execute

### Start server on localhost:8080

```bash
python3 templating.py -t ../tech-templates/ -c config.yaml
```

### Run a template once with options

```bash
python3 ../templating/templating.py --once magic.conf -c templating/config.yml -t . -i switch=e7-4
```

## Mitigate SSTI Vulnerability

This service exposes a api endpoit where you can POST a template and have it rendered.
To mitigate the obvious SSTI this creates, please but the endpoint behind authentication.
