#!/bin/bash
cd "$(dirname "$0")"
cd mdvbrec/
echo $(pwd)
python RecorderWebServer.py
