'''run tests in docker container'''

import docker
import yaml
import logging
import json
import sys
import glob
import os.path
import subprocess
from urllib.parse import urlparse, urlunparse
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


def git_checkout(url, branch):
    gitdir = 'cibox-git'

    logger.debug("looking for %s in remote repository", branch)
    ls = subprocess.Popen(['git', 'ls-remote', url, branch],
                          stdout=subprocess.PIPE)
    (out, err) = ls.communicate()
    if ls.returncode != 0:
        raise Exception("ls-remote failed")

    sha = out.decode('utf-8').split('\n')[0].strip('\n').split('\t')[0]

    if not os.path.exists(gitdir):
        subprocess.check_call(['git', 'init', '--bare', gitdir])

    logger.debug("fetching %s", sha)
    subprocess.check_call(['git', '--git-dir', gitdir, 'fetch', url, sha])

    @contextmanager
    def read_file(path):
        read = subprocess.Popen(['git', '--git-dir', gitdir,
                                 'show', '%s:%s' % (sha, path)
                                ],
                                stdout=subprocess.PIPE)
        read.wait()
        if read.returncode != 0:
            raise FileNotFoundError("Failed to read %s" % path)
        yield read.stdout


    @contextmanager
    def archive():
        read = subprocess.Popen(['git', '--git-dir', gitdir, 'archive', sha],
                                stdout=subprocess.PIPE)
        read.wait()
        if read.returncode != 0:
            raise FileNotFoundError("Failed to read %s" % path)
        yield read.stdout

    return read_file, archive


def load_config(read_file, defaults):
    '''Look for configuration by a few alternative names'''

    for cname in ('.cibox.yml', '.travis.yml'):
        logger.debug("looking for config in %s", cname)
        try:
            with read_file(cname) as cfg:
                return parse_config(cfg, defaults)
        except FileNotFoundError as e:
            continue
    else:
        raise Exception("No configuration file found in %s" % pdir)


def parse_config(stream, defaults):
    config = yaml.load(stream)

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
        host_config=client.create_host_config(binds=binds))
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

    read_file = None
    workdir = None

    components = urlparse(args.repository)
    if components.scheme != '':
        # Load from a git url
        branch = components.fragment or 'master'
        url = urlunparse(components[:5] + ('',))
        read_file, archive = git_checkout(url, branch)
    else:
        # Load local file
        workdir = args.repository
        read_file = lambda path: open(os.path.join(workdir, path), 'r')

    config = load_config(read_file, defaults)

    client = docker.Client(base_url=args.docker)

    image = select_image(config)
    ensure_image(client, image)

    with container(client, image, workdir) as cnt:
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


if __name__ == '__main__':
    main()
