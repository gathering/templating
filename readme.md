# Templating Service

THIS HAS NOT BEEN TESTED VERY MUCH, YET :) #alpha/beta/something

This is a new version of our templating engine!

There's one weird thing, to be a bit backwards compatible the last two items of a path will be used as the objects name.

This however opens up for possible name collisions from files and http api data.

Example:

```
---
get:
  - file:///root/templating/data/read/networks.yaml
  - file:///root/templating/data/read/networks.json
  - https://<USER:PW>@gondul.tg23.gathering.org/api/read/networks
  - http://<USER:PW>@gondul.tg23.gathering.org/api/read/networks
```

All of these would be added as `read/networks` in the python dicts. Aka, the last one is going to win.
Therefor, think twice when naming things :)

## Features

- Loads data from local files
  - yaml
  - json
- Loads data from API's

## Currently supported URI locations

- `file://`
  - Can be both a file, or a folder
  - We will attempt to load all files found recursively
- `https://` and `http://`
  - Gets data from API endpoint

## Example file

```yaml
---
get:
  - file:///root/templating/data
  - https://<USER:PW>@gondul.tg23.gathering.org/api/read/networks
```
