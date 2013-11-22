#!/bin/bash
# possible commands are: getEpg | showJobs
cd "$(dirname "$0")"
cd mdvbrec/
python RecorderDaemon.py $1
