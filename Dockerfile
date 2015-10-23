FROM python:3.4
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
COPY defaults /defaults/
COPY ci.py /cibox
ENTRYPOINT ["/cibox"]
