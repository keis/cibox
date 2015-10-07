'''run tests in docker container'''

import docker
import yaml
import logging
import json
import sys
import glob
import os.path
from contextlib import contextmanager
from functools import partial

logging.basicConfig(level='DEBUG')
logger = logging.getLogger(__name__)

config_keys = (
    'before_install',
    'install',
    'before_script',
    'script',
    'after_success',
    'after_failure',
    'after_script'
)


class ScriptError(Exception):
    pass


def create_defaults_repository(globexp):
    defaults = {}

    for f in glob.glob(globexp):
        with open(f, 'r') as cfg:
            config = yaml.load(cfg)
            defaults[config['language']] = config

    return defaults


def load_config(path, defaults):
    with open(path, 'r') as cfg:
        config = yaml.load(cfg)

    try:
        default_config = defaults[config['language']]
    except KeyError:
        raise Exception('Unsupported language {language}'.format(**config))

    config['image'] = default_config['image']

    for key in config_keys:
        val = config.get(key, default_config[key])
        if not isinstance(val, list):
            val = [val]
        config[key] = val

    return config


@contextmanager
def container(client, image, workdir):
    c = client.create_container(
        image=image, command='/bin/sleep 10m', volumes=['/cibox'],
        working_dir='/cibox',
        host_config=docker.utils.create_host_config(binds={
            workdir: {
                'bind': '/cibox',
                'mode': 'rw'
            }
        }))
    client.start(container=c['Id'])
    try:
        yield c
    except:
        logger.error("An error occured", exc_info=True)
    finally:
        client.kill(container=c['Id'])


def execute(client, container, cmd):
    logger.info("executing %s", cmd)
    e = client.exec_create(container=container['Id'],
                           cmd=['/bin/bash', '-c', cmd])

    for up in client.exec_start(exec_id=e['Id'], stream=True):
        sys.stdout.write(up.decode('utf-8'))
    info = client.exec_inspect(exec_id=e['Id'])
    if info['ExitCode'] != 0:
        raise ScriptError("Script exited with {ExitCode}".format(**info))


def fold_script(config, script, fun):
    logger.info("runnings script for `%s` stage", script)
    for cmd in config[script]:
        fun(cmd)


def select_image(config):
    return config['image']


def ensure_image(client, image):
    try:
        client.inspect_image(image)
    except docker.errors.NotFound:
        for up in client.pull(image, stream=True):
            data = json.loads(up.decode('utf-8'))
            print(data['status'])


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=str,
                        help='path to code repository')
    parser.add_argument('--docker', type=str,
                        help='base url for docker client')
    args = parser.parse_args()

    defaults = create_defaults_repository('./defaults/*.yml')

    pdir = args.repository

    # Look for configuration by a few alternative names
    for cname in ('.cibox.yml', '.travis.yml'):
        try:
            config = load_config(os.path.join(pdir, cname), defaults)
            break
        except FileNotFoundError as e:
            continue
    else:
        print("No configuration file found in %s" % pdir, file=sys.stderr)
        sys.exit(1)

    client = docker.Client(base_url=args.docker)
    image = select_image(config)

    ensure_image(client, image)

    with container(client, image, pdir) as cnt:
        run = partial(execute, client, cnt)
        logger.debug("got a container %s", cnt['Id'])

        fold_script(config, 'before_install', run)
        fold_script(config, 'install', run)
        fold_script(config, 'before_script', run)

        try:
            fold_script(config, 'script', run)
        except:
            fold_script(config, 'after_failure', run)
        else:
            fold_script(config, 'after_success', run)

        fold_script(config, 'after_script', run)


if __name__ == '__main__':
    main()
