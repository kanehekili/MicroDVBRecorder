#!/bin/bash
# possible commands are: getEpg | showJobs
ldlib=/opt/lib/libmediaclient.so
cd "$(dirname "$0")"
cd mdvbrec/
if [ -f "$ldlib" ]
then
   export LD_PRELOAD=$ldlib
   echo Preloaded: $LD_PRELOAD
fi

python3 RecorderDaemon.py $1
