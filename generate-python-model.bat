@echo off

docker run --rm -v "%~dp0:/local" openapitools/openapi-generator-cli:latest generate ^
    -g python-fastapi ^
    -o /local/simpler-model ^
    -c /local/generate-python-model-config.yaml
