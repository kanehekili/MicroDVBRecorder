# -*- coding: utf-8 -*-
'''
Created on Oct 27, 2013
contains the OS calls for a linux OS 
@author: matze
'''
import os
import subprocess
from subprocess import Popen
from datetime import timedelta
from datetime import datetime
import logging
try:
    import dbus
except ImportError:
    print "No dbus support"    


RTC_SLEEP="mem"
RTC_HIBERNATE="disk"
RTC_NO="no"
RTC_ON="on"
RTC_SHUTDOWN="off"


def checkIfInstanceRunning(moduleName):
    process = Popen(["ps aux |grep -v grep | grep "+moduleName],shell=True,stdout=subprocess.PIPE)
    result = process.communicate()
    rows = result[0].split('\n')
    instanceCount =0;
    for line in rows:
        if line:
            instanceCount+=1
    return instanceCount == 1

    #TODO: Not working if no x-server!    
def blankScreen():
    Popen(["xset","dpms","force","off"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()

def getProcessPID(processName):
    result = Popen(["pidof",processName],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
    if len(result[0])==0:
        return None
    texts = result[0].split('\n')
    return texts[0]

def isXServerRunning():
    try:
        os.environ['DISPLAY']
        return True
    except:
        return False

def killProcess(pid):
    if len(pid)>0:
        result = Popen(["kill","-9",str(pid)],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
        logging.log(logging.INFO,"kill process :"+str(result[1]))

def getDirectorySize(recPath):
    dirInfo,dirError = Popen(["du","-s",recPath],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()  
    #parse the result
    numberString = dirInfo.split("\t")[0]
    try:
        ret = int(numberString)
    except ValueError:
        logging.log(logging.ERROR,"Disk use failed:"+str(dirError))
        ret =0

    return ret             

def getDifferenceInSeconds(lateTime,earlyTime):
    td = lateTime -earlyTime
    return (td.days * 3600 * 24) + td.seconds

def convertSecondsToString(secs):
    prefix=""
    if secs < 0:
        secs = abs(secs)
        prefix="-"
    td = timedelta(seconds=secs)
    return prefix+str(td)

#display the current date + added seconds as human readable string
def showDateTimeWithOffset(seconds):
    return getDateTimeWithOffset(seconds).strftime(" %d.%m-%H:%M.%S")
    
def getDateTimeWithOffset(seconds):
    return datetime.now()+timedelta(seconds=seconds)

def addToDateTime(aDateTime, seconds ):
    return aDateTime + timedelta(seconds=seconds)

def syncFiles():
    Popen(["sync"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()

'''
Note: This only runs in X session
'''
def saveEnergyDbus(shouldHibernate):
    bus = dbus.SystemBus()
    power = bus.get_object('org.freedesktop.UPower','/org/freedesktop/UPower')
    iface = dbus.Interface(power, 'org.freedesktop.UPower')
    if (shouldHibernate):
        iface.Hibernate()
    else:
        iface.Suspend()

#undocumented feature -1        
def saveEnergy(rtcMode):
    rtcWake(-1, rtcMode)  
     
'''
 wakes up after given secondsToWait.
 Uses one of the OSTools RTC Modes
'''
def rtcWake(secondsToWakeup,rtcMode):
    secondStr=str(secondsToWakeup)
    return Popen(["sudo","rtcwake","-s",secondStr,"-m",rtcMode],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()


def ensureDirectory(path,tail):
    #make sure the target dir is present
    if tail is not None:
        path = os.path.join(path,tail)
    if not os.access(path, os.F_OK):
        try:
            os.makedirs(path)
            os.chmod(path,0o777) #This took half a night!
        except OSError as osError:
            logging.log(logging.ERROR,"target not created:"+path)
            logging.log(logging.ERROR,"Error: "+ str(osError.strerror))

def ensureFile(path,tail):
    fn = os.path.join(path,tail)
    ensureDirectory(path, None)
    with open(fn, 'a'):
        os.utime(fn, None)
    return fn
    

def fileExists(path):
    return os.path.isfile(path)

def removeFile(path):
    os.remove(path);

'''
answers the last modification time in seconds 
throws OSError
'''
def getLastModificationTime(path):
    if fileExists(path):
        statbuf = os.stat(path)
        return statbuf.st_mtime
    return 0.0
        
class Inhibitor:
    #That is NOT desktop agnostic..... so check if ok
    __SERVICE = 'org.gnome.SessionManager'
    __SERVICE_URL= '/org/gnome/SessionManager'
    def __init__(self):
        if not isXServerRunning():
            self.cookie = -1
        else:
            self.__setCookie()
        
    
    def __setCookie(self):
        bus = dbus.SessionBus()
        if self.__isUsable(bus):
            proxy = bus.get_object (self.__SERVICE,self.__SERVICE_URL)
            self.sessionManager = dbus.Interface (proxy, self.__SERVICE)
            self.cookie = 0
        else:
            self.cookie = -1
        
    def inhibit_gnome_screensaver(self, toggle):
        if self.cookie==-1:
            return
        if toggle == True:
            self.cookie = self.sessionManager.Inhibit("inhibit.py",0,"Manual override",8)
        else:
            self.sessionManager.Uninhibit (self.cookie)
        
    def __isUsable(self,sessionBus):
        aList = sessionBus.list_activatable_names()
        return self.__SERVICE in aList   
    
