#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Created on Oct 11, 2012

@author: matze
'''
import sys
from ChannelReader import ChannelReader
from EpgReader import ReaderThread
from EPGProgramProvider import EPGProgramProvider
from Configuration import Config,MessageListener
from VideoRecorderView import RecorderView
import OSTools
import DVBDevice


class DVBRecorder():
    '''
    startup main class
    '''

    def __init__(self):
        '''
        starts the app
        '''
        self.configuration = Config()
        self.configuration.setupLogging("dvb.log")
        
        channelReader = ChannelReader()
        cPath = self.configuration.getChannelFilePath()

        channelReader.readChannels(cPath)
        self.channelList = channelReader.getChannels()
        self.progProvider = EPGProgramProvider(self,self.channelList,self.configuration)
        recView = RecorderView(self.progProvider)
        ml = MessageListener();
        ml.addListener(ml.MSG_STATUS, recView.setStatusLine)
        ml.addListener(ml.MSG_EPG, recView.notifyEPGStatus)
        ml.addListener(ml.MSG_REFRESH, recView.refreshProgrammInfos)
        t1 = ReaderThread(False,self._readCachedEpgData)
        t1.start()
        recView.openView();
        #returns on close
        t1.join()

  
    def _readCachedEpgData(self):
        ml = MessageListener();
        if not self.channelList:
            ml.signalMessage(ml.MSG_STATUS,"Where is that channel.conf? RTF!")
            return

        ml.signalMessage(ml.MSG_STATUS,"Reading programm info")
        msg = "Idle"
        try:
            self.progProvider.readEPGCache()
            ml.signalMessage(ml.MSG_REFRESH)# enforces a new list
        except IOError:
            msg = "No EPG data"
        except Exception,ex:
            msg= "Error reading cached EPG Data: "+str(ex.args[0])

        self.configuration.logInfo(msg)                        
        ml.signalMessage(ml.MSG_STATUS,msg)
        
    ##callback for the epg program provider:
    def readEPGDeviceData(self):
        self._EPGThread = ReaderThread(False,self._collectEPGFromDevice)
        #TEST code: self._EPGThread = ReaderThread(False,self._readEPGSimData)
        self._EPGThread.start()


    def _collectEPGFromDevice(self):
        ml = MessageListener();
        ml.signalMessage(ml.MSG_EPG,True)
        ml.signalMessage(ml.MSG_STATUS,"Retrieving new EPG data")
        
        epgUpdater = self.progProvider.getEPGUpdater()
        epgUpdater.updateDatabase();
        if epgUpdater.hasError():
            ml.signalMessage(ml.MSG_STATUS,epgUpdater.getErrorMessage())
            ml.signalMessage(ml.MSG_EPG,False)
            return;
        
        ml.signalMessage(ml.MSG_REFRESH)# enforces redraw!    
        ml.signalMessage(ml.MSG_STATUS,"EPG data up to date !")
        ml.signalMessage(ml.MSG_EPG,False)

  
  
#    def _readEPGSimData(self):
#        rawEPGPath = "/home/matze/JWSP/py1/VideoRecorder/src/xmltv/rawepg.xmltv"
#        with open(rawEPGPath, 'r') as aFile:
#            dvbList=aFile.readlines()
#
#        epgReader=EpgReader(self.channelList)
#        for xmls in dvbList:
#            print "parse xml"    
#            epgReader.parseXML_TVString(xmls,UTC=True)
#            
#        infoDictionary = epgReader.getInfoDictionary()
#        self.progProvider.updateProgramms(infoDictionary)
#        ml = MessageListener(); 
#        ml.signalMessage(ml.MODE_REFRESH)# enforces redraw!    
#        ml.signalMessage(ml.MODE_STATUS,"EPG data up to date !")
#        ml.signalMessage(ml.MODE_EPG,False)

          
    def _getEPGDevice(self):
        return DVBDevice.getGrabber(self.channelList,self.configuration)
    
    
    def persistEPGData(self):
        self.configuration.logInfo("Saving data...")
        epgUpdater = self.progProvider.getEPGUpdater()
        self.progProvider.getAutoSelector().saveAutoSelectData()
        epgUpdater.persistDatabase()
        if epgUpdater.hasError():
            self.configuration.logError("Error saving xml data")

        
#def runEnergySaver(path,recorder):
#    import subprocess
#    subprocess.Popen(["python",path],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
#    recorder.configuration.logInfo("Spawned Energy saver")
  
def main(argv = None):
    if OSTools.checkIfInstanceRunning("DVBRecorder"):
        recorder = DVBRecorder();
        recorder.persistEPGData()
        ##TODO: Store config data
#        if recorder.configuration.STATE_USE_ENERGY_SAVER:
#            path = recorder.configuration.HomeDir+"/EnergySaver.py"
#            runEnergySaver(path,recorder)
        recorder.configuration.logInfo("Exit")
        recorder.configuration.logClose()
              
    print "Goodbye"

 
    
if __name__ == '__main__':
    sys.exit(main())            