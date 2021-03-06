#!/usr/bin/env python3
'''run tests in docker container'''

import docker
import yaml
import logging
import json
import sys
import glob
import os.path
import subprocess
import shlex
from urllib.parse import urlparse, urlunparse
from contextlib import contextmanager
from functools import partial
from collections import defaultdict
from itertools import product, cycle

logging.basicConfig(level='DEBUG')
logger = logging.getLogger('cibox')

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
    defaults = defaultdict(dict)

    for f in glob.glob(globexp):
        with open(f, 'r') as cfg:
            config = yaml.load(cfg)
            lang = config['language']
            alt = config.get(lang, 'default')
            defaults[lang][alt] = config

    return defaults


def git_checkout(url, branch):
    gitdir = 'cibox-git'

    logger.debug("looking for %s in remote repository", branch)
    ls = pipe_process(['git', 'ls-remote', url, branch])
    sha = ls.read().decode('utf-8').split('\n')[0].strip('\n').split('\t')[0]

    if not os.path.exists(gitdir):
        pipe_process(['git', 'init', '--bare', gitdir]).read()

    logger.info("fetching %s", sha)
    pipe_process(['git', '--git-dir', gitdir, 'fetch', url, branch]).read()

    @contextmanager
    def read_file(path):
        yield pipe_process(['git', '--git-dir', gitdir, 'show', '%s:%s' % (sha, path)])

    @contextmanager
    def archive():
        yield pipe_process(['git', '--git-dir', gitdir, 'archive', sha])

    return read_file, archive


def pipe_process(command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process_stream(p, p.stdout, p.stderr, command, logger)


class process_stream(object):
    def __init__(self, process, stream, errstream, command_info, logger):
        self.name = command_info[0]
        self.process = process
        self.stream = stream
        self.errstream = errstream
        self.command_info = command_info
        self.logger = logger

    def read(self, *args):
        process = self.process
        r = self.stream.read(*args)

        for l in self.errstream.readlines(256):
            self.logger.debug('%s! %s', self.name, l.decode('utf-8').strip('\n'))

        if len(r) == 0:
            process.wait()
        else:
            process.poll()

        if process.returncode is not None and process.returncode != 0:
            for l in self.errstream.readlines():
                self.logger.debug('%s! %s', self.name, l.decode('utf-8').strip('\n'))
            raise subprocess.CalledProcessError(process.returncode,
                                                self.command_info)

        return r


def load_config(read_file, defaults):
    '''Look for configuration by a few alternative names'''

    for cname in ('.cibox.yml', '.travis.yml'):
        logger.debug("looking for config in %s", cname)
        try:
            with read_file(cname) as cfg:
                return parse_config(cfg, defaults)
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    else:
        raise Exception("No configuration file found")


def as_list(val):
    if not isinstance(val, list):
        return [val]
    return val


def parse_config(stream, defaults):
    config = yaml.load(stream)
    lang = config['language']
    alts = as_list(config.get(lang, 'default'))
    envs = as_list(config.get('environment', ''))

    configs = []
    for alt, env in product(alts, envs):
        try:
            default_config = defaults[lang][alt]
        except KeyError:
            raise Exception('Unsupported language {language}'.format(**config))

        aconfig = dict(config, environment=env)
        aconfig['image'] = default_config['image']

        for key in config_keys:
            aconfig[key] = as_list(config.get(key, default_config[key]))

        configs.append(aconfig)

    return configs


@contextmanager
def container(client, image, workdir, environment):
    if workdir is not None:
        binds = {
            workdir: {
                'bind': '/cibox',
                'mode': 'rw'
            }
        }
    else:
        binds = None

    c = client.create_container(
        image=image, command='/bin/sleep 10m', volumes=['/cibox'],
        working_dir='/cibox',
        environment=environment,
        host_config=client.create_host_config(binds=binds))
    client.start(container=c['Id'])
    try:
        yield c
    except:
        logger.error("An error occured", exc_info=True)
    finally:
        client.kill(container=c['Id'])


def execute(client, container, cmd, logger):
    logger.info("executing %s", cmd)
    e = client.exec_create(container=container['Id'],
                           cmd=['/bin/bash', '-c', cmd])

    for up in client.exec_start(exec_id=e['Id'], stream=True):
        logger.info(up.decode('utf-8').strip('\n'))
    info = client.exec_inspect(exec_id=e['Id'])
    if info['ExitCode'] != 0:
        raise ScriptError("Script exited with {ExitCode}".format(**info))


def fold_script(config, script, fun):
    logger.info("running script for `%s` stage", script)
    slog = logging.getLogger('cibox.{}'.format(script))
    for cmd in config[script]:
        fun(cmd, slog)


@contextmanager
def status_spinner():
    def inner(message):
        sys.stdout.write("\033[1K\r[{}] {}".format(next(s), message))

    s = cycle('.oO@* ')
    yield (inner if sys.stdout.isatty() else lambda m: None)
    print()


def ensure_image(client, image):
    try:
        client.inspect_image(image)
    except docker.errors.NotFound:
        logger.info('pulling %s from registry', image)
        with status_spinner() as sp:
            for up in client.pull(image, stream=True):
                try:
                    data = json.loads(up.decode('utf-8'))
                    sp(data['status'])
                except:
                    pass


def repository(path):
    components = urlparse(path)

    if components.scheme != '':
        # Load from a git url
        branch = components.fragment or 'master'
        url = urlunparse(components[:5] + ('',))
        read_file, archive = git_checkout(url, branch)
        return (None, read_file, archive)

    # Load local file
    workdir = path
    return (
        workdir,
        (lambda path: open(os.path.join(workdir, path), 'r')),
        None
    )


def run_tests(client, workdir, archive, config):
    image = config['image']
    logger.info('preparing to run tests in %s', image)
    ensure_image(client, image)
    env = shlex.split(config['environment'])

    with container(client, image, workdir, env) as cnt:
        if workdir is None:
            with archive() as tar:
                data = tar.read()
            client.put_archive(cnt, '/cibox', data)

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


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=str,
                        help='path to code repository')
    parser.add_argument('--docker', type=str,
                        help='base url for docker client')
    parser.add_argument('--matrix-id', type=int,
                        help='sub-build of matrix build to run')
    args = parser.parse_args()

    defaults = create_defaults_repository('./defaults/*.yml')
    workdir, read_file, archive = repository(args.repository)
    config = load_config(read_file, defaults)

    if args.matrix_id is None and len(config) > 1:
        print("{} build variations specify which with --matrix-id".format(len(config)),
              file=sys.stderr)
        sys.exit(1)
    else:
        config = config[args.matrix_id or 0]

    client = docker.Client(base_url=args.docker, version='auto')
    run_tests(client, workdir, archive, config)


if __name__ == '__main__':
    main()
