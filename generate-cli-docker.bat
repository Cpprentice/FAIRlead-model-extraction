@echo off

set dt=%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%T%TIME:~0,2%-%TIME:~3,2%-%TIME:~6,2%
set dt=%dt: =0%

REM echo %dt%

docker build -f %~dp0\Dockerfile-CLI -t simpler-cli:%dt% %~dp0
