#!/usr/bin/python3

import argparse
import traceback
import sys
import os
import errno

import aiohttp
import asyncio

import netaddr

import aiofiles

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

def load_conf_file(config_file):
   with open(config_file, "r") as f:
       config = yaml.load(f.read(), Loader=yaml.CSafeLoader)
   return config


async def getEndpoint(session, url, **options):
    async with session.get(url, timeout=args.timeout, **options) as resp:
        try:
            resp_body = await resp.json(content_type=None)
        except:
            resp.raise_for_status()
        return url, resp_body


async def loadUrls(urls):
    async with aiohttp.ClientSession() as session:

        tasks = []
        for i in urls:
            options = dict(list(i.values())[0])
            url = list(i.keys())[0]
            tasks.append(asyncio.ensure_future(getEndpoint(session, url, **options)))

        responses = await asyncio.gather(*tasks)
        for response in responses:
            key = '/'.join(urlparse(response[0]).path.split('/')[-2:])
            objects[key] = response[1]
    return 1


async def readFile(file):
    async with aiofiles.open(file, mode='r') as f:
        content = await f.read()
        out = yaml.load(content, Loader=yaml.CSafeLoader)
        return file, out

async def loadFiles(files):
    tasks = []
    for file in files:
        options = list(file.values())[0]
        file = list(file.keys())[0]
        if is_yaml:
            pass
        else:
            raise ValueError(
                f'Failed to load {file}. Not a JSON or YAML formatted file')
        tasks.append(asyncio.ensure_future(readFile(file)))

    contents = await asyncio.gather(*tasks)
    for content in contents:
        objects[createObjName(content[0])] = content[1]
    return 1


async def runTasks(tasks):
    await asyncio.gather(*tasks)


def updateData():

    config = load_conf_file(args.config)

    files_tasks = []
    urls_tasks = []
    for item in config["get"]:
        if isinstance(item, dict):
            pass
        elif isinstance(item, str):
            item = {item: ''}
        else:
            sys.exit(f"{item} is not a str, or dict. Exit")
        
        options = list(item.values())[0]
        item = list(item.keys())[0]
        item = urlparse(item)

        if item.scheme == "file":
            # Make this a function again, someday
            path = item.netloc + item.path
            if not os.path.isabs(path):
                path = os.path.normpath(os.getcwd() + item.path)
            if os.path.isdir(path):

                for subdir, dirs, files in os.walk(path):
                    for file in files:
                        path = os.path.join(subdir, file)
                        d = {path: options}
                        files_tasks.append(d)
            elif os.path.isfile(path):
                d = {path: options}
                files_tasks.append(d)
            else:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), path)

        elif item.scheme == "https" or item.scheme == "http":
            item = item.geturl()
            d = {item: options}
            urls_tasks.append(d)

    tasks = []
    tasks.append(loadUrls(urls_tasks))
    tasks.append(loadFiles(files_tasks))
    asyncio.run(runTasks(tasks))


 
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
    return render_template(path, options=request.args)

def render_template(tpl, options):
    try:
        updateData()
        template = env.get_template(tpl)
        body = template.render(objects=objects, options=options)
    except (aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientResponseError) as err:
        return f'Connection error trying to get: {err}', 500
    except TemplateNotFound:
        return f'Template "{tpl}" not found\n', 404
    except TemplateError as err:
        return f'Templating of "{tpl}" failed to render. Most likely due to an error in the template. Error transcript:\n\n{err}\n----\n\n{traceback.format_exc()}\n', 400
    except FileNotFoundError as err:
        return f'File error: {err}', 500
    except ValueError as err:
        return f'Parsing Error: {err}', 500
    except Exception as err:
        print(traceback.format_exc())
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
parser.add_argument("-x", "--timeout", type=int, default=20,
                    help="gondul server timeout")
parser.add_argument("-o", "--once", type=str, default="",
                    help="Run once with the provided template")
parser.add_argument("-i", "--options", type=str, default="", nargs="+",
                    help="Options to send to template, like query params in the API")
parser.add_argument("-f", "--outfile", type=str, default="",
                    help="Output file, otherwise prints to stdout")
parser.add_argument("--help",  type=str, default="",
                    help="Print help")

try:
    args = parser.parse_args()
except:
    parser.print_help()
    sys.exit(0)

env.loader.searchpath = args.templates


if not sys.argv[1:]:
    parser.print_help()
    sys.exit(1)

if args.once:
    options = {}
    for option in args.options:
        key, value = option.split('=')
        options[key] = value
    body, _ = render_template(args.once, options=options)
    if args.outfile:
        with open(args.outfile, 'w') as f:
            f.write(body)
    else:
        print(body)
    sys.exit(0)

app.run(host=args.host, port=args.port, debug=args.debug)
