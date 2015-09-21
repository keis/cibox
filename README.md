# cibox

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
docker build -t cibox_nodejs docker/nodejs
```

## Usage

```bash
python ci.py /path/to/repo/.travis.yml unix:///run/docker.sock
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
