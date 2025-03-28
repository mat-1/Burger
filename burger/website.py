#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
Copyright (c) 2011 Tyler Kenendy <tk@tkte.ch>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import json
import os
import urllib.request

VERSION_MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'

_cached_version_manifest = None
_cached_version_metas = {}


def _load_json(url):
    stream = urllib.request.urlopen(url)
    try:
        return json.load(stream)
    finally:
        stream.close()


def get_version_manifest():
    global _cached_version_manifest
    if _cached_version_manifest:
        return _cached_version_manifest

    _cached_version_manifest = _load_json(VERSION_MANIFEST)
    return _cached_version_manifest


def get_version_meta(version: str, verbose: bool):
    """
    Gets a version JSON file, first attempting the to use the version manifest
    and then falling back to the legacy site if that fails.
    Note that the main manifest should include all versions as of august 2018.
    """

    if version in _cached_version_metas:
        return _cached_version_metas[version]

    version_manifest = get_version_manifest()
    for version_info in version_manifest['versions']:
        if version_info['id'] == version:
            address = version_info['url']
            break
    else:
        raise Exception(f'Failed to find {version} in the main version manifest.')
    if verbose:
        print(f'Loading version manifest for {version} from {address}')
    meta = _load_json(address)

    _cached_version_metas[version] = meta
    return meta


def get_asset_index(version_meta, verbose):
    """Downloads the Minecraft asset index"""
    if 'assetIndex' not in version_meta:
        raise Exception('No asset index defined in the version meta')
    asset_index = version_meta['assetIndex']
    if verbose:
        print('Assets: id %(id)s, url %(url)s' % asset_index)
    return _load_json(asset_index['url'])


def client_jar(version: str, verbose: bool):
    """Downloads a specific version, by name"""
    filename = f'{version}.jar'
    if not os.path.exists(filename):
        meta = get_version_meta(version, verbose)
        if verbose:
            print(
                f'For version {filename}, the downloads section of the meta is {meta["downloads"]}'
            )
        url = meta['downloads']['client']['url']
        if verbose:
            print(f'Downloading {version} from {url}')
        urllib.request.urlretrieve(url, filename=filename)
    return filename


def mappings_txt(version: str, verbose: bool):
    """Downloads the mappings for a specific version, by name"""
    filename = f'{version}-mappings.txt'
    if not os.path.exists(filename):
        meta = get_version_meta(version, verbose)
        if verbose:
            print(
                f'For version {filename}, the downloads section of the meta is {meta["downloads"]}'
            )
        url = meta['downloads']['client_mappings']['url']
        if verbose:
            print(f'Downloading {version} mappings from {url}')
        urllib.request.urlretrieve(url, filename=filename)
    return filename


def latest_client_jar(verbose):
    manifest = get_version_manifest()
    return client_jar(manifest['latest']['snapshot'], verbose)
