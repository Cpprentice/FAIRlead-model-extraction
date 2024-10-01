@echo off

docker run --rm -v "%~dp0:/local" redocly/cli bundle /local/spec/0/openapi3_1.yaml -o /local/spec/0/openapi3_1_merged.yaml

docker run --rm -v "%~dp0:/local" openapitools/openapi-generator-cli:latest generate ^
    -g python-fastapi ^
    -o /local/simpler-api ^
    -c /local/generate-python-api-config.yaml
