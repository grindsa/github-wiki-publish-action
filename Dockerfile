FROM alpine/git:latest

RUN apk add --no-cache bash python3
COPY entrypoint.sh publish_wiki.py /
RUN chmod +x /entrypoint.sh /publish_wiki.py

ENTRYPOINT ["/entrypoint.sh"]
