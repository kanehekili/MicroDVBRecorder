#!/bin/bash
channel=$1
ldlib=/opt/lib/libmediaclient.so
if [ -f "$ldlib" ]
then
   export LD_PRELOAD=$ldlib
   echo Preloaded: $LD_PRELOAD
fi
czap -x -n "$channel"
