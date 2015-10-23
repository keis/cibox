.PHONY: docker

DOCKERTAG?=cibox

docker:
	docker build -t ${DOCKERTAG} .
