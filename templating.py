#!/usr/bin/python3

import argparse
import traceback
import sys
import os
import errno

import netaddr
import requests

from pathlib import Path

import yaml
from urllib.parse import urlparse

from flask import Flask, request
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateError

from datetime import datetime

objects = {}

def try_as(loader, s, on_error):
    try:
        loader(s)
        return True
    except on_error:
        return False

def is_yaml(s):
    return try_as(yaml.cSafeLoader, s, yaml.scanner.ScannerError)

def createObjName(i):
    return str(Path(*Path(os.path.splitext(i)[0]).parts[-2:]))

def loadFile(file):
    if is_yaml:
        pass
    else:
        raise ValueError(f'Failed to load {file}. Not a JSON or YAML formatted file')
    with open(file, 'r') as f:
        d = yaml.load(f.read(), Loader=yaml.CSafeLoader)
        objects[createObjName(file)] = d

def getEndpoint(uri: str) -> dict:
    """
    Fetches an endpoint and returns the data as a dict.
    """
    r = requests.get(uri, timeout=args.timeout)
    r.raise_for_status()
    return r.json()

def loadUri(u):
    a = '/'.join(u.path.split('/')[-2:])
    objects[a] = getEndpoint(u.geturl())

def load(i):
    if i.scheme == "file":
        path = i.netloc + i.path
        if not os.path.isabs(path):
            path = os.path.normpath(os.getcwd() + i.path)
        if os.path.isdir(path):
            for subdir, dirs, files in os.walk(path):
                    for file in files:
                        loadFile(os.path.join(subdir, file))
        elif os.path.isfile(path):
            loadFile(path)
        else:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)
    elif i.scheme == "https" or i.scheme == "http":
        loadUri(i)


def load_conf_file(config_file):
   with open(config_file, "r") as f:
       config = yaml.load(f.read(), Loader=yaml.CSafeLoader)
   return config

def updateData():
    config = load_conf_file(args.config)
    for i in config["get"]:
        load(urlparse(i))
 
env = Environment(extensions=['jinja2.ext.do'], loader=FileSystemLoader([]), trim_blocks=True, lstrip_blocks=True)

env.filters["netmask"] = lambda ip: netaddr.IPNetwork(ip).netmask
env.filters["cidr"] = lambda ip: netaddr.IPNetwork(ip).prefixlen
env.filters["networkId"] = lambda ip: netaddr.IPNetwork(ip).ip
env.filters["getFirstDhcpIp"] = lambda ip: netaddr.IPNetwork(ip)[2]
env.filters["getLastDhcpIp"] = lambda ip: netaddr.IPNetwork(ip)[-2]
env.filters["getIp"] = lambda ip, num: netaddr.IPNetwork(ip)[num]
env.filters["agentDistro"] = lambda src: src.split(":")[0]
env.filters["agentPort"] = lambda src: src.split(":")[1]
env.filters["getFirstFapIP"] = lambda ip: netaddr.IPNetwork(
    ip)[netaddr.IPNetwork(ip).size / 2]

env.tests['inList'] = lambda list, item: True if item in list else False

app = Flask(__name__)


@app.after_request
def add_header(response):
    if response.status_code == 200:
        response.cache_control.max_age = 5
        response.cache_control.s_maxage = 1
    return response


@app.route("/<path>", methods=["GET"])
def root_get(path):
    try:
        updateData()
        template = env.get_template(path)
        body = template.render(objects=objects, options=request.args)
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as error:
        return f'Timeout or connection error from gondul: {err}', 500
    except TemplateNotFound:
        return f'Template "{path}" not found\n', 404
    except TemplateError as err:
        return f'Templating of "{path}" failed to render. Most likely due to an error in the template. Error transcript:\n\n{err}\n----\n\n{traceback.format_exc()}\n', 400
    except requests.exceptions.HTTPError as err:
        return f'HTTP error from gondul: {err}', 500
    except FileNotFoundError as err:
        return f'File error: {err}', 500
    except ValueError as err:
        return f'Parsing Error: {err}', 500
    except Exception as err:
        return f'Uncaught error: {err}', 500
    return body, 200


@app.route("/<path>", methods=["POST"])
def root_post(path):
    try:
        updateData()
        content = request.stream.read(int(request.headers["Content-Length"]))
        template = env.from_string(content.decode("utf-8"))
        body = template.render(objects=objects, options=request.args)
    except Exception as err:
        return 'Templating of "{path}" failed to render. Most likely due to an error in the template. Error transcript:\n\n{err}\n----\n\n{traceback.format_exc()}\n', 400
    return body, 200


parser = argparse.ArgumentParser(
    description="Process templates for gondul.", add_help=False)
parser.add_argument("-t", "--templates", type=str,
                    nargs="+", required=True, help="location of templates")
parser.add_argument("-c", "--config", type=str,
                    default="config.yaml", required=True, help="Location of config file")
parser.add_argument("-h", "--host", type=str,
                    default="127.0.0.1", help="host address")
parser.add_argument("-p", "--port", type=int, default=8080, help="host port")
parser.add_argument("--debug", action="store_true",
                    help="enable debug mode")
parser.add_argument("-x", "--timeout", type=int, default=2,
                    help="gondul server timeout")

args = parser.parse_args()
env.loader.searchpath = args.templates

if not sys.argv[1:]:
    parser.print_help()
    sys.exit(1)

app.run(host=args.host, port=args.port, debug=args.debug)
