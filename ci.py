import docker
import yaml
import logging
import json
import sys
import os.path
from contextlib import contextmanager
from functools import partial

logging.basicConfig(level='DEBUG')
logger = logging.getLogger(__name__)

nodejs_config = {
    'before_install': [],
    'install': ['npm install'],
    'before_script': [],
    'script': ['npm test'],
    'after_success': [],
    'after_failure': [],
    'after_script': []
}

config_keys = tuple(nodejs_config.keys())


class ScriptError(Exception):
    pass


def load_config(path):
    with open(path, 'r') as cfg:
        config = yaml.load(cfg)

    if config['language'] == 'node_js':
        default_config = nodejs_config
    else:
        raise Exception('Unsupported language {language}'.format(**config))

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
    if config['language'] == 'node_js':
        return 'cibox_nodejs'
    return 'busybox'


def ensure_image(client, image):
    try:
        client.inspect_image(image)
    except docker.errors.NotFound:
        for up in client.pull(image, stream=True):
            data = json.loads(up.decode('utf-8'))
            print(data['status'])


def main():
    pdir = os.path.dirname(sys.argv[1])
    config = load_config(sys.argv[1])

    client = docker.Client(base_url=sys.argv[2])
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
