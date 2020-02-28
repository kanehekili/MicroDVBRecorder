MicroDVBRecorder
================
Version 3.1.2

![Download](https://github.com/kanehekili/MicroDVBRecorder/blob/master/VideoRecorder/build/mdvbrec3.1.2.tar)

DVB-T/C Recording Daemon + Webservice  Runs on Linux X86 and arm

![Screenshot](https://github.com/kanehekili/MicroDVBRecorder/blob/master/Recorder.png)

MicroDVB Recorder has been written for recording TV films from dvb devices. The software uses the EPG Data contained in the TV Stream to update its program guide.<br>
The EPG grabbing code (tv_Grab_dvb)  has been taken and adapted from http://bryars.eu/projects/tv_grab_dvb/

In order to use the Recorder the following prerequisites have to be met:
* dvb-apps or equivalent 
* rtcwake (only if VCR mode is used)
* tmux - if you want to keep the sessions on a server (optional)
* Firmware for you DVB stick or a Sundtek driver if using a Sundtek Stick

### Preparing the DVB system:
Download the "dvb-apps" package. It usually come with a commandline tool called _w_scan_.

MDVBRecorder needs a channel list in *zap format, so in order to retrieve the channels install your DVB-stick, connect it to the device and execute:

<code>w_scan -f c -x -c de</code> (de is for Germany, use your country code )

The resulting file needs to be in one of the follwing directories in "home":<br>
.tzap\channels.conf<br>
.czap\channels.conf

The channels.conf is the base for getting the EPG data as well as the recording. Prior to starting the recorder please check if it works:
czap "ZDF" or tzap "ARD" or whatever channel names you have.

### Preparing the executables
Unpack the _mdvbrec.tar_ file (found in the _build_ folder) to a dedicated folder (i.e Recorder) and make the following files executable:
* mdvbrec\bin czapRecord.sh,
* tv_grab_dvb
* all sh files in that folder using "chmod+x"

In case you are using a Sundtek Media Pro DVB Stick it is strongly recommended to download the drivers and install them with:
<br><code>./sundtek_netinst.sh -system</code>
<br>The necessary "LD_PRELOAD" export is included in all relevant executables.

### Configuring the basics
MDVBRec needs to know which kind of device it should use. Edit the config file "xmltv/config.xml". Tested are TZAP and CZAP. Plugins may be written to support more devices
<br>*ONE OF "TZAP" "CZAP" or "SUNDTEK_C")
<br>RECORD_TYPE = CZAP
<br>*Indicates where the files should be stored:
<br>RECORDING_PATH = /home/Video/recme
<br>Note: Due to problems running the dvb apps on arm an additional support for Sundteks Mediaclient has been created.I've been using the hardware from https://shop.sundtek.de/startseite/ since 5 years and can recommend it....

Recorder Daemon
---------------
The deamon can be started with the "startDaemon.sh"

If all prerequisites are met it will start reading the EPG data, which might take up to 10 minutes. If done the deamon will now wait until a recording is scheduled.
<br>The daemon will create folders named as the channel. Its file names will contain a time stamp and the title.
<br>An additional "info.txt" file lists the descriptions per file.
<br>The type of file may either be mp2 (transport stream) or AVCHD (mp4 transport Stream)

### Converting/Handling
<br>SD: mp2 ts files can be cut & converted with DVBCut. Very convinient an fast.
<br>HD: mp4 ? Im working on a VideoCut right now. Until then you may cut the files and convert them using ffmpeg.
<br>Tip (fastseek): ffmpeg -ss 00:05:30.00 -i in.m2t -t 00:29:00 -vcodec copy  -acodec copy out.mp4

WebServer
---------
As frontend a Webserver must be startet, using the "startWebServer.sh"
<br>It starts with User Test Passwd Test on port 8080. Authentication will not be required, if the web server is called from the local network. 
<br>Enter the follwing URL in your favourite browser (no- not IE ):
<br>ipaddress:8080/
<br>You should see the channels as well as the program list 

#### GTK GUI (not working with python 3 anymore -deprecated)
You may use a GTK application instead of the webserver. A desktop file can be found in the "mdvbrec.tar". Copy it to .local/share/applications.


MDVBREC Interface
-----------------
* Antenna:      Open/Collapse the channel pane (More space on mobile use)
* Green Arrows: Move up and down one day
* Magn. Glas:   Search a title on any channel
* Filter:       If a title has been selected, shows all other of that channel (if they exist)
* Book:         The log file
* Film clip:    Lists all entered recordings. Select one recording to change the prerun/postrun minutes
* Robo:         By dragging a progamm info onto the Robo icon it will record that titel whenever it is encountered in the future. Note that the titel must reappear at the same hour...

### Recording
Double click on a programm item will put it in the record queue. An icon might show that this timeslot is already taken.

Arm support
-----------
The recorder runs also (daemon and web server) on a cubieboard or rasberry pi. If you use an arm device, replace tv_grab_dvb with the /arm/tv_grab_dvb version by copying it.
Note that there is no support for "openelec" yet - there are plans to change that.

### Keeping the sessions with tmux
If tmux is installed you can use tmuxStart.sh to run both daemon and webserver in a session. Whenever you log in via ssh on the device the session can be restored with "tmux a"
<br>In the tmux window the sessions can be supervised or killed (use crtl+c)


VCR Mode
---------
If you are using a Laptop or worse you may activate the VCR Mode.
<br>The mode will put the computer to sleep until the next recording. After the recording, it will sleep again, so saving some energy (and noise)
<br>Note that the webserver will also not be available at that time...
<br>If turned on again (e.g by liftig the lid) the Recording deamon will go into Server mode - so VCR mode has to be switched on again.
<br>For this mode these files help:
* ./serverModeOn switches from VCR mode to server mode
* ./sleepModeOn switches to VCR Mode. The computer will, if not just recording, be put into sleep.

#### Note for VCR Policy
In order to run this daemon the /etc/sudoer file has to be changed:
<p>xUser ALL=NOPASSWD: /usr/sbin/rtcwake</p>
<p>Defaults:xUser !requiretty</p>
<p>where xUser is the owner of that account(otherwise sudo will no work in applications)</p>

.
----
## Touch support for Chrome on Android (Apple not tested)
### Changing the order of Channels 
* Touch the channel to move - press until its text color turns yellow. Move it into the desired position, indicated by a blue line.

### Programm handling
* Recording - Press/Tab the left column until the text color turns yellow. On release you will see an icons indicating that the programm will be recorded
* Add to auto selection - In case you want a programm to be recorded regularly press it until its text color gets yellow and drag it ro the monitor icon, droip it there

### Removing entries in the Recording List or Autorec list
* Swipe the entry from left to right or vice versa until it gets marked. On release it will be removed

----- 
The software has been used for over 5 years now- it is stable..
