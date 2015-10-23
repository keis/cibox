FROM python:3.4
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
COPY defaults /defaults/
COPY cibox /cibox
ENTRYPOINT ["/cibox"]
