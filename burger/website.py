import json
import logging
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


def get_version_meta(version: str):
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
    logging.debug(f'Loading version manifest for {version} from {address}')
    meta = _load_json(address)

    _cached_version_metas[version] = meta
    return meta


def get_asset_index(version_meta):
    """Downloads the Minecraft asset index"""
    if 'assetIndex' not in version_meta:
        raise Exception('No asset index defined in the version meta')
    asset_index = version_meta['assetIndex']
    logging.debug(f'Assets: id {asset_index["id"]}, url {asset_index["url"]}')
    return _load_json(asset_index['url'])


def client_jar(version: str):
    """Downloads a specific version, by name"""
    filename = f'{version}.jar'
    if not os.path.exists(filename):
        meta = get_version_meta(version)
        logging.debug(
            f'For version {filename}, the downloads section of the meta is {meta["downloads"]}'
        )
        url = meta['downloads']['client']['url']
        logging.info(f'Downloading {version} from {url}')
        urllib.request.urlretrieve(url, filename=filename)
    return filename


def mappings_txt(version: str):
    """Downloads the mappings for a specific version, by name"""
    filename = f'{version}-mappings.txt'
    if not os.path.exists(filename):
        meta = get_version_meta(version)
        logging.debug(
            f'For version {filename}, the downloads section of the meta is {meta["downloads"]}'
        )
        url = meta['downloads']['client_mappings']['url']
        logging.info(f'Downloading {version} mappings from {url}')
        urllib.request.urlretrieve(url, filename=filename)
    return filename


def latest_client_jar():
    manifest = get_version_manifest()
    return client_jar(manifest['latest']['snapshot'])
