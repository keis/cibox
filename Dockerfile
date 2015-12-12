FROM alpine:3.2
RUN apk add --update musl python3 git && \
    rm -rf /var/cache/apk/*
COPY requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt
COPY defaults /defaults/
COPY ci.py /cibox
ENTRYPOINT ["/cibox"]
