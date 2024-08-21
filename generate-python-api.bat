@echo off

docker run --rm -v "%~dp0:/local" openapitools/openapi-generator-cli:latest generate ^
    -g python-fastapi ^
    -o /local/simpler-api ^
    -c /local/generate-python-api-config.yaml
