#!/bin/bash
SESSION=rec
#get the current directory
DIR="$(dirname "$0")"
tmux start-server
# if the session is already running, just attach to it.
tmux has-session -t $SESSION
if [ $? -eq 0 ]; then
       echo "Session $SESSION already exists. Attaching."
       sleep 1
       tmux attach -t $SESSION
       exit 0;
fi

# create a new session, named $SESSION, and detach from it
tmux new-session -d -s $SESSION -n 'Daemon' 
# split into 2 panes vertically window 0
tmux split-window  -v -t 0
tmux new-window    -n 'Web Server' 
#select the only window ...
tmux select-window -t 0
#issue the commands for pane 0 and 1
tmux send-keys -t 0 $DIR/startDaemon.sh C-m
tmux send-keys -t 1 $DIR/startWebServer.sh C-m
#make the top pane the selected one...
tmux select-pane -t 0
#and attach the session
tmux a
