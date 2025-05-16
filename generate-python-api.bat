@echo off

docker run --rm -v "%~dp0:/local" redocly/cli bundle /local/spec/0/openapi3_1.yaml -o /local/spec/0/openapi3_1_merged.yaml

docker run --rm -v "%~dp0:/local" openapitools/openapi-generator-cli:latest generate ^
    -g python-fastapi ^
    -o /local/simpler-api ^
    -c /local/generate-python-api-config.yaml

docker run --rm -v "%~dp0:/local" -w /local linkml/linkml:1.8.7 linkml generate doc -d spec_markdown/docs spec/0/ero-custom.yaml

docker run --rm -v "%~dp0:/local" -w /local/spec_markdown squidfunk/mkdocs-material:9.6.14 build -d /local/simpler-api/static/ontology-docs

copy "%~dp0\spec\0\ero.ttl" "%~dp0\simpler-api\static\raw\ero.ttl"

docker run --rm -v "%~dp0:/local" -w /local linkml/linkml:1.8.7 linkml generate jsonld-context spec/0/ero-custom.yaml > %~dp0\simpler-api\static\raw\context.jsonld