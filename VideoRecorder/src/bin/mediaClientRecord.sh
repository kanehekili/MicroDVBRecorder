#!/bin/bash
#record channel for a given time 
#run mediaclient for locking and recording
#channels.conf is expected in local .czap directory
#parameters are: 1)durance in seconds 2)target path 3 channelfreq 4)Qam 5)SymbolRate 6)programID
#opt/bin/mediaclient -m DVBC -f 3940000000 -M Q256 -S 6900000
#opt/bin/mediaclient --tsprogram 53602 -d /dev/dvb/adapter0/dvr0 > "${target}

durance=$1
freq=$2
qam=$3
symbolrate=$4
progID=$5
target=$6

echo rec channelid: $progID to target $target durance $durance seconds
/opt/bin/mediaclient -m DVBC -f "$freq" -M "$qam" -S "$symbolrate" > /dev/null &
zap_pid=$!

sleep 2
if ! ps -p $zap_pid ; then
	echo "tuning failed"
	exit 1
fi
# Adapter is dvr0
/opt/bin/mediaclient --tsprogram "$progID" -d /dev/dvb/adapter0/dvr0 > "${target}" &
rec_pid=$!

trap "kill $rec_pid" SIGINT SIGTERM EXIT
sleep $durance
echo "Rec done"
