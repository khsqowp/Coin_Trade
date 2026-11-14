#!/bin/bash
# Full regression in an offline locked-down container.
cd "$(dirname "$0")"
docker run --rm --network none --entrypoint python -v $PWD/src:/app/src:ro -v $PWD/tests:/app/tests:ro -v $PWD/strategy_library:/app/strategy_library:ro -v $PWD/strategy_pool:/app/strategy_pool:ro --tmpfs /tmp --read-only -e PYTHONDONTWRITEBYTECODE=1 tp-pipeline:local -m pytest -q -p no:cacheprovider /app/tests "$@"
