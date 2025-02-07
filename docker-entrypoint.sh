#!/bin/bash
set -e

# Generate config.ini from template using environment variables
envsubst < config.template.ini > config.ini

exec "$@"