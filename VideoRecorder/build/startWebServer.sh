#!/bin/bash
cd "$(dirname "$0")"
cd mdvbrec/
echo $(pwd)
python3 RecorderWebServer.py 8080 Test:Test
