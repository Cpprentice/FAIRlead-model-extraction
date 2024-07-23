@echo off

docker run --rm -v "%~dp0:/local" redocly/cli bundle /local/spec/0/openapi3_1.yaml -o /local/spec/0/openapi3_1_merged.yaml

docker run --rm -v "%~dp0:/local" openapitools/openapi-generator-cli:latest generate ^
    -g python-fastapi ^
    -o /local/simpler-model-3_1 ^
    -c /local/generate-python-model-config-3_1.yaml
