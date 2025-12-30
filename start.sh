#!/bin/bash

#DISCORD_KEY=
#OPENAI_API_KEY=

docker container stop eldrida || true
docker container rm eldrida || true

VERSION=$1

docker build . --file Dockerfile --tag carequinha/eldrida:"$VERSION"
docker run -d \
--name eldrida \
-e DISCORD_KEY=$DISCORD_KEY \
-e OPENAI_API_KEY=$OPENAI_API_KEY \
--restart always \
carequinha/eldrida:"$VERSION"