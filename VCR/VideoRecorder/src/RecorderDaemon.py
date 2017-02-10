#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Oct 5, 2013

@author: matze

Daemon replacing the EngergySaver
Basic functions:
1)read EPGData from file, extract the Data from the RecordQueue
2)starts a socket on port 6001 to listen if data has been changed. (Initiated by GTK oder Webserver client)
3)calculates the time to the next recording, using the "Adjacent" info
4)Sleeps/hibernates if so configured..

Note for VCR Policy
#########################################################################
In order to run this daemon the /etc/sudoer file has to be changed:
xUser ALL=NOPASSWD: /usr/sbin/rtcwake
Defaults:xUser !requiretty 
where xUser is the owner of that account(otherwise sudo will no work in applications)
#########################################################################
'''

import subprocess
from subprocess import Popen
from datetime import datetime
import logging
import re
import time as xtime
from Configuration import Config
from EpgUpdate import EpgUpdater
import sys
import DVBDevice
import OSTools


class RecorderDaemon():
    LOG_FILE = "dvb_suspend.log"
    HEARTBEAT = 60
    DAY_IN_SECONDS = 60*60*24
    EPG_UPDATE_INTERVAL = DAY_IN_SECONDS+10
    EPG_TS_Template = '%Y%m%d%H%M%S'
    
    def __init__(self,):
        self._config = Config()
        self._setUpLogging()
        self.epgUpdater = EpgUpdater(self._config)
        OSTools.ensureDirectory(self._config.getRecordingPath(),'')
        self._inhibitor = OSTools.Inhibitor()
        self._recordCmd = DVBDevice.getRecordCommander()
        self._lastJobId="0"
        self._recordPartIndex=0
        self.isActive=True
        self._daemonPolicy = None
   

    def _getNextJob(self):
        return self.epgUpdater.getRecordQueue().getNextRecordingEntry()

    def _updateEPGData(self):
        days = self._getDaysSinceLastEPGUpdate()
        if days == 0:
            self._log("EPG is up to date")
            return False
        self._log("Last EPG update %s day(s) ago - Updating now.."%str(days))
        self.epgUpdater.updateDatabase()
        if  self.epgUpdater.hasError():
            self._log("EPG Update failed: "+self.epgUpdater.getErrorMessage())
            return False

        self.epgUpdater.persistDatabase()
        currentDate= datetime.now().strftime(self.EPG_TS_Template)
        path = self._config.getEPGTimestampPath()
        with open(path,'w') as f:
            f.write(currentDate)
        return True
    
    '''
    Enforce a epg data read
    '''
    def readEPGData(self):
        path = self._config.getEPGTimestampPath() 
        if OSTools.fileExists(path):
            OSTools.removeFile(path)
        self._updateEPGData()
    

    def _getDaysSinceLastEPGUpdate(self):
        path = self._config.getEPGTimestampPath()
        if OSTools.fileExists(path):
            with open(path, 'r') as aFile:
                currentDate=aFile.read()
            try:
                checkDate = datetime.strptime(currentDate,self.EPG_TS_Template)
                delta = datetime.now()-checkDate
                return delta.days
            except ValueError:
                self._log("Error reading EPG Timestamp:"+str(currentDate))
        return -1

    def _isTimeLeftForEPGUpdate(self,nextStartTime):
        now = datetime.now()
        seconds = OSTools.getDifferenceInSeconds(nextStartTime, now)
        return seconds > self.HEARTBEAT*10

    def _secondsUntilNextRun(self,startTime,prerunSeconds):
        now = datetime.now()
        secondsUntilStart = OSTools.getDifferenceInSeconds(startTime, now)
        secondsToSleep = secondsUntilStart - prerunSeconds #wake up a minute+ before
        if secondsToSleep < prerunSeconds:
            self._log("Next run in less than %s seconds"%(str(secondsUntilStart))) #sleep until time is ready.... no hibernate
            if secondsUntilStart > 0:
                self._log("Waiting to launch...."+str(secondsUntilStart))
                xtime.sleep(secondsUntilStart)
            return 0
        return secondsToSleep
    
    
    def launchRecording(self,recInfo):
        #As opposed to a previous version no AT queue is used. Reason: recording needs to be supervised 
        #anyhow, so there is need for a supervising/scheduling process
        channel = recInfo.getEPGInfo().getChannel()
        OSTools.ensureDirectory(self._config.getRecordingPath(),channel.getEscapedName())
        jobID= recInfo.getEPGInfo().getJobID()
        self._syncRecordIndex(jobID)
        scheduler= Recorder(self._config,self._recordCmd,self._recordPartIndex)
        return scheduler.scheduleRecording(recInfo)            

    def _stopQueue(self):
        self.isActive=False
        
    def _exit(self):
        self._inhibitor.inhibit_gnome_screensaver(False)
        self._stopQueue()
        self._log("exit daemon")
        logging.shutdown()


    def _setUpLogging(self):
        path = self.LOG_FILE
        self._config.setupLogging(path)
        
    def _log(self,aString):
        self._getLogger().log(logging.INFO,aString)
        print aString

    def _getLogger(self):
        return logging.getLogger('dvb_scheduler')
    
    
    def _hasRecordingProcess(self):
        pidInfo = OSTools.getProcessPID(self._recordCmd.Command)
        if pidInfo is None:
            xtime.sleep(2) # in case of adjacent films
            pidInfo = OSTools.getProcessPID(self._recordCmd.Command)
  
        return pidInfo is not None 

    '''
    If that recInfo has been killed previously due to a bad reception increment the recordIndex which will
    be used for a unique title for a retry (therefore not overwriting already existing recordings)
    '''        
    def _syncRecordIndex(self,jobID):
        if self._lastJobId == jobID:
            self._recordPartIndex=self._recordPartIndex+1
        else:
            self._recordPartIndex=0
            self._lastJobId = jobID
            

    def _monitorCurrentRecording(self,recProcess,recordingJob):
        done = False
        #this is testing:
        emergencyCount=0;
        
        jobID=recordingJob.getEPGInfo().getJobID()
        isRecurrentWriteError=False
        recPath = self._config.getRecordingPath()
        videoSize=OSTools.getDirectorySize(recPath)
        xtime.sleep(self.HEARTBEAT)
        self._log("Monitoring JOB "+jobID)
        while not done:
            result = recProcess.poll()
            isAlive = result is None
            if isAlive:
                currentSize = OSTools.getDirectorySize(recPath)
                delta = currentSize - videoSize
                print "JOB "+jobID+" - bytes written:"+str(delta) #live sign- not logging
                videoSize = currentSize
                if delta == 0:
                    self._log("JOB "+jobID+" does not write any data")
                    if isRecurrentWriteError:
                        done=True
                        self._log("Terminating Rec process, preventing reschedule.. ")
                        recProcess.terminate()
                        self.__handleProcessTermination(recProcess)
                    isRecurrentWriteError=True #only on retry permitted
            else:
                self._log("Quit JOB "+jobID)
                self.__handleProcessTermination(recProcess)
                done=True
                
            if not done:
                #Ensure that an adjacent job can follow - decrease the wait time
                delta = max(10,OSTools.getDifferenceInSeconds(recordingJob.getEndTime(),datetime.now()))
                sleepTime = min(self.HEARTBEAT,delta)
                if sleepTime != self.HEARTBEAT:
                    emergencyCount+=1;
                    self._log("stopping in seconds:"+str(sleepTime))#log only the fragments
                    if emergencyCount > 10:
                        self._log("REC Q error- force process termination")
                        recProcess.terminate()
                        self.__handleProcessTermination(recProcess)
                        done=True
                xtime.sleep(sleepTime)
                
        self._log("JOB "+jobID+" is done")
        OSTools.syncFiles()
    
    def __handleProcessTermination(self,recProcess):
        result=recProcess.communicate()
        potentialErrorMessage = result[1].strip()
        msg =">>"+result[0].strip()+" status:"+potentialErrorMessage
        #TODO: check for errors ggf boolean back - cancel recording if necessary
        if "ERROR" in potentialErrorMessage:
            print "TODO Unhandled {c,t}ZAP error!"
        self._log(msg)
        
    
    def _initializePolicy(self):
        if Config.DAEMON_POLICY == Config.POLICY_SERVER:
            self._setServerPolicy()
        else:
            self._setVCRPolicy()
    
    def _setServerPolicy(self):
        self._daemonPolicy = ServerPolicy(self)

    def _setVCRPolicy(self):
        self._daemonPolicy = VCRPolicy(self)
        
    
    def _isPolicyChangeRequested(self,markerFile):
        if OSTools.fileExists(markerFile):
            OSTools.removeFile(markerFile)
            return True
        return False
    
    '''
    if a file is present with the name of "SaveEnergy" remove it and switch to VCR mode
    '''
    def isVCRPolicyChangeRequested(self):
        markerFile= self._config.getEnergySaverFileMarker()
        if self._isPolicyChangeRequested(markerFile):
            self._setVCRPolicy()
            return True
        return False
    
    def isServerPolicyChangeRequested(self):
        markerFile= self._config.getServerFileMarker()
        if self._isPolicyChangeRequested(markerFile):
            self._setServerPolicy()
            return True
        return False
    
    
    
    
    def _startDaemon(self):
        errorCount =0;
        while self.isActive and errorCount < 10:
            try:
                #Always a job, possibly a maintenance for epg update
                nextJob =self._getNextJob()
                startTime = nextJob.getExecutionTime()
                if self._isTimeLeftForEPGUpdate(startTime):
                    if self._updateEPGData():
                        continue #maybe a fresh job came in...
                secondsToSleep = self._secondsUntilNextRun(startTime,self._daemonPolicy.PRERUN_SECONDS)
                if self._daemonPolicy.isReadyToRecord(startTime,secondsToSleep):
                    if nextJob.getEPGInfo() is None:
                        self._log("Maintenance mode- will update EPG")
                        continue;
                    process = self.launchRecording(nextJob)
                    self._monitorCurrentRecording(process,nextJob)

            except KeyboardInterrupt:
                print '^C received, shutting down daemon'
                self._exit()

            except Exception,ex:
                msg= "Error running SuspensionDaemon: "+str(ex.args[0])
                self._getLogger().exception(msg)
                print msg
                errorCount = errorCount + 1
            
    def run(self):
        self._log("Starting daemon..")
        self._inhibitor.inhibit_gnome_screensaver(True)
        self.epgUpdater.readEPGCache()
        self._initializePolicy()
        self._startDaemon()
        

#---------- Daemon end -------------------


'''
Scheduling policies:
Server: polls but keeps server alive
VCR:sleeps,switches to Server mode if awakened prematurely, exits & hibernates if no jobs are available 
'''
class VCRPolicy():
    def __init__(self,recDaemon):
        self._daemon=recDaemon
        self.PRERUN_SECONDS = 240 #!IMPORTANT! Devices need to init
    
    def handleNoJobs(self):
        if self._daemon.isServerPolicyChangeRequested():
            return;
        self._daemon._stopQueue() #make sure in case that hibernation fails and logging is still active
        OSTools.saveEnergy(OSTools.RTC_HIBERNATE)
        self._daemon._exit()

    #Ready to run: True if woke up on schedule, false on user interaction
    def isReadyToRecord(self,startTime,secondsToWait):
        if secondsToWait==0:
            return True
        if self._daemon.isServerPolicyChangeRequested():
            return False

        self._suspendDevice(secondsToWait)
        isScheduled =  self._wasWakeupScheduled(startTime)
        if not isScheduled:
            self._daemon._setServerPolicy()
        return isScheduled

        
    def _wasWakeupScheduled(self,startTime):
        now = datetime.now()
        secondsToWait = OSTools.getDifferenceInSeconds(startTime, now)
        duranceStr = OSTools.convertSecondsToString(secondsToWait)
        self._log("Delta durance to scheduled wakeup:"+duranceStr)
        
        if secondsToWait > self.PRERUN_SECONDS:
            self._log("Suspend interrupted by user-> going into Server mode!")
            return False
        if secondsToWait>0:
            self._log("Waiting until record starts:"+duranceStr)
            xtime.sleep(secondsToWait)
        return True

    def _suspendDevice(self,seconds):
        coolDown=20 #mediaclient needs time to shutdown
        duranceStr = OSTools.convertSecondsToString(seconds)
        self._log("Going to sleep for %s" %(duranceStr))
        logging.shutdown();
        xtime.sleep(coolDown)
        mode = OSTools.RTC_SLEEP
        if Config.SUSPEND_MODE == Config.MODE_HIBERNATE:
            mode=OSTools.RTC_HIBERNATE
        result=OSTools.rtcWake(seconds-coolDown, mode)
        #back online
        self._daemon._setUpLogging()
        self._log(str(result[0])+":"+str(result[1]))        
        self._log("Woke up")

    
    def _log(self,aString): 
        self._daemon._log(aString)   

                
class ServerPolicy():        
    def __init__(self,recDaemon):
        self._daemon = recDaemon
        self.PRERUN_SECONDS=1

    #read epg after 24 hrs     
    def handleNoJobs(self):  
        self._argusWait(RecorderDaemon.EPG_UPDATE_INTERVAL)

    def isReadyToRecord(self,startTime,secondsToWait):
        if secondsToWait==0:
            return True
        isReady =  self._argusWait(secondsToWait)
        return isReady
             
    def _argusWait(self,secondsToWait):
        startTime = datetime.now() 
        
        #self._log("Observing recorder queue for %s. Use 'sleepModeOn' for VCR mode"%OSTools.convertSecondsToString(secondsToWait))
        self._log("Observing recorder queue until %s. Execute 'sleepModeOn' for VCR mode"%OSTools.showDateTimeWithOffset(secondsToWait))
        lastQCheck=None
        while (OSTools.getDifferenceInSeconds(datetime.now(),startTime) < secondsToWait):
            xtime.sleep(self.PRERUN_SECONDS)
            path=self._config().getRecQueuePath()
            try:
                currentModificationTime=OSTools.getLastModificationTime(path)
            except OSError as osError:
                currentModificationTime=0.0
                self._config().logError("Error checking rec file:"+osError.strerror) 
                print "Error checking rec file"                       
            #check for socket or file changes... 
            if lastQCheck is None:
                lastQCheck=currentModificationTime #we came from a queue check-so thats the last time we checked 
            if currentModificationTime-lastQCheck>0:
                self._log("Rec Q modified-looking for jobs")
                return False
            if self._daemon.isVCRPolicyChangeRequested(): 
                return False
 
        return True


    def _config(self):
        return self._daemon._config

    def _log(self,aString):    
        self._daemon._log(aString)
    
'''
Recorder is responsible to start a recording, adding infos  
'''
class Recorder():
    def __init__(self,config,recordingDevice,recordIndex):
        self._config=config
        self._recDevice=recordingDevice
        self._recordFileIndex=recordIndex
        
                                
    def scheduleRecording(self,recInfo):
        if recInfo is None:
            return None
        args = self._generateCommand(recInfo)
        #cmdText = ' '.join(args)
        return self._executeRecording(args,recInfo.getExecutionTime())

 
    def _generateCommand(self,recInfo):
        epgInfo = recInfo.getEPGInfo()
        channel = epgInfo.getChannel()
        channelName = channel.getEscapedName()
        
        #String for filename
        startTimeString=epgInfo.getStartTime().strftime("%m_%d_%H_%M-")
        recPath = self._config.getRecordingPath() 
        path = self._config.getFilePath(recPath, channelName)
        fileExt=self._config.MPGFileTyp
        cleanTitle = epgInfo.getTitle().strip()
        cleanTitle = re.sub('[\\/:"*?<>|%]+', '', cleanTitle)
        if self._recordFileIndex>0:
            cleanTitle=cleanTitle+"_"+str(self._recordFileIndex)
        fileName = self._config.getFilePath(path,startTimeString+cleanTitle+fileExt)
        #Recorder selection
        argList = self._recDevice.getArguments(epgInfo, recInfo.getDurance(),fileName)
        #Save Title and description in an info file at path
        self._saveRecordInfo(path,epgInfo,startTimeString)
        return argList
 

    #store title and description -entries will not be removed! 
    def _saveRecordInfo(self,path,epgProgramInfo,startTimeString):
        filePath = self._config.getFilePath(path,"Info.txt")
        try:
            with open(filePath, 'a') as aFile:
                aFile.write(startTimeString+" ")
                text = epgProgramInfo.getTitle()
                aFile.write(text+" -- ")
                text = epgProgramInfo.getDescription()
                aFile.write(text+'\n')
        except IOError,ioex:
            msg = "I/O error saving Recinfo ({0}): {1}".format(ioex.errno, ioex.strerror)
            self._config.logError(msg)
            print msg
        
        except Exception, ex:
            msg = "Unknown error saving Recinfo: "+str(ex.args[0])
            self._config.logError(msg+" Record Info:"+epgProgramInfo.getChannel().getName()+"-"+epgProgramInfo.getStartTimeString())
            print msg
                             
    def _executeRecording(self,args,scheduleTime):
        timeString = scheduleTime.strftime("%H:%M %b %d")
        process = Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE, shell=False)
        cmdText=' '.join(args)
        print "dispatched command::"+cmdText
        self._config.logInfo("command sent: \n"+cmdText+" | scheduled at:"+timeString)
        #TODO: process still alive - even if done -- still syncing???
        return process

def main():

    argv = sys.argv
    if len(argv)==1:
        RecorderDaemon().run()
    else:
        cmd = argv[1]
        if "epg" in cmd.lower():
            RecorderDaemon().readEPGData()
            return 0;
        if "job" in cmd.lower():
            job = RecorderDaemon()._getNextJob()
            if job is None:
                print "No jobs pending"
            else:
                print "Next Job @"+str(job.getExecutionTime())
            return 0; 
        
        print "start daemon with no args.. Use 'getEpg' to read EPG or 'showJobs' for pending jobs"
        return 1;
if __name__ =="__main__":
    if OSTools.checkIfInstanceRunning("RecorderDaemon"):
        OSTools.changeWorkingDirectory(OSTools.getWorkingDirectory())
        sys.exit(main())
    else:
        print "Daemon already running..." 