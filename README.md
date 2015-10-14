# cibox

[![Build Status][travis-image]](https://travis-ci.org/keis/cibox)

A test runner for any language. It uses docker to create a container that will
run the tests while keeping the control flow outside. This puts minimal
restraints on the image as does not need do anything but run the normal
commands for the target language.

cibox uses some travis idioms for convenience but full compatibility is not a
goal.

Currently this is only a *proof-of-concept* and only supports a basic nodejs
setup. Feedback is welcome (pull requests doubly so)

## Setup

```bash
virtualenv --python python3.4 env
source env/bin/activate
pip install -r requirements.txt
```

## Usage

build from a local directory

```bash
python ci.py /path/to/repo/
```

or from a git repository
```bash
python ci.py git+ssh://git@github.com/user/repo.git#branch
```

## Tests

There is a few rudimentary tests written for cibox which of course can be run
by cibox so that you can test that it can test and also run the tests

```bash
python ci.py "file:///$(pwd)"
```

## Notes
http://docs.travis-ci.com/user/customizing-the-build/
https://github.com/docker/docker-py

* parse yaml
* start container of specified type
* start executers in turn from the life cycle inside the container (defaults + configured)
 - before_install
 - install
 - before_script
 - script
 - after_success / afer_failure
 - after_script

[travis-image]: https://img.shields.io/travis/keis/cibox.svg?style=flat
