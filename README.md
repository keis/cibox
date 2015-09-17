# cibox

CI with a travis like life-cycle

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
