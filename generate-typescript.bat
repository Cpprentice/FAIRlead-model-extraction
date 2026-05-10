@echo off

docker run --rm -v "%~dp0:/local" redocly/cli bundle /local/spec/0/openapi3_1.yaml -o /local/spec/0/openapi3_1_merged.yaml

docker run --rm -v "%~dp0:/local" openapitools/openapi-generator-cli:latest generate ^
    -g typescript-fetch ^
    -o /local/typescript ^
    -c /local/generate-typescript-fetch-config.yaml

pushd %cd%\typescript

REM del /S /Q schema_api*.tgz
REM pnpm pack

popd
