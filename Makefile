.PHONY: docker

DOCKERTAG?=cibox
DEFAULTSRC=$(shell find defaults)
DEFAULTS=${DEFAULTSRC:%=docker/%}

docker: docker/requirements.txt docker/cibox ${DEFAULTS}
	cp -r defaults docker
	docker build -t ${DOCKERTAG} docker

docker/defaults:
	mkdir -p $@

docker/defaults/%: defaults/%
	cp $^ $@

docker/requirements.txt: requirements.txt
	cp $^ $@

docker/cibox: ci.py
	cp $^ $@
