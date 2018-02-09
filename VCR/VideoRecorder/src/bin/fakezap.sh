#!/bin/bash
#fake a recording for a given time
#commands are: 1)durance in seconds 2)target path

durance=$1
target=$2


#trap durance=0 SIGHUP SIGINT SIGTERM SIGKILL
echo record to target: $target for $durance seconds

START=`date +%s`
while [ $(( $(date +%s) - $durance )) -lt $START ]; do
  fillText=$(for i in {1..10000};do printf "%s" "#";done;printf "x")
  echo Tick $(date) $fillText >> "${target}"
  echo Tick $(date '+%Y-%m-%d %H:%M.%S')
  sleep 5
done

