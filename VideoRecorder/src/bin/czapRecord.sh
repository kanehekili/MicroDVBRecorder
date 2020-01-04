#!/bin/bash
#record channel for a given time 
#run czap + cat the data
#channels.conf is expected in local .czap directory
#commands are: 1)durance in seconds 2)target path 3)channel name
#czap -r -p -c c_channels.conf "ZDF HD"
#cat /dev/dvb/adapter0/dvr0 > superrtl.m2t

durance=$1
target=$2
channel=$3
#Note: this is a subprocess! export should defined at the main program
#export LD_PRELOAD=/opt/lib/libmediaclient.so
echo record channel: $channel to target $target durance $durance seconds
czap -r -p "$channel" > /dev/null &
czap_pid=$!
sleep 2
if ! ps -p $czap_pid ; then
	echo "tuning failed"
	exit 1
fi
# Adapter should be configurable!
cat /dev/dvb/adapter0/dvr0 > "${target}" &
rec_pid=$!

trap "kill $rec_pid $czap_pid" SIGINT SIGTERM EXIT
sleep $durance
echo "Rec done"
