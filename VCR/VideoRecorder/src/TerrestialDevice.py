# -*- coding: utf-8 -*-
'''
Created on Oct 19, 2012

@author: matze
'''
import time as xtime
import subprocess
from subprocess import Popen
from Configuration import MessageListener, Config

class DVB_T_Grabber:
    '''
    Grabs the data from a DVB-T device using "tzap" and tv_grab_dvb
    both applications need to have a channels.conf which should be located at ~/.tzap
    '''    
 
    def __init__(self,channelList,configuration):
        self.channelInfos = channelList;
        self._frequencyBlocks=self._collectBlocks()
        self.configuration = configuration
                
    def _collectBlocks(self):
        cBlocks = {}
        for channel in self.channelInfos:
            cBlocks.setdefault(channel.getFrequency(),channel.getName())
            
        return cBlocks.values()    
    
    #reads data from a channel and returns the XML data
    def _collectEPGFromDevice(self,channelName):
        try:
            tzapProcess = Popen(["tzap","-F","-s",channelName],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            xtime.sleep(3)
            pathToGrab = self.configuration.getBinPath()
            cmd = self.configuration.getFilePath(pathToGrab,"tv_grab_dvb")
            processResult=Popen([cmd,"-t 20","-s"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
            tzapProcess.terminate()
            tzapInfo = tzapProcess.communicate() #Closes the process, preventing a zombie
            tzapErrorIndex=tzapInfo[1].rfind("ERROR")
            if tzapErrorIndex==-1:
                return processResult[0]
        except OSError as osError:
            errorCode = "OSError - tzap or tv_grab not found:"+osError.strerror
            self.configuration.logError(errorCode)
            print errorCode
            raise Exception(errorCode)
        except:
            raise Exception("Unknown Device Error");
        
        #error tzap
        errorMsg = tzapInfo[1][tzapErrorIndex:]
        raise Exception("tzap: "+errorMsg)

        
    '''
    collect all the info available- returns a List of xmldata
    each entry may be parsed by the EpgReader
    '''    
    def collectEPGList(self):
        epgBlockData = []
        ml = MessageListener()
        for channelName in self._frequencyBlocks:
            xmlData = self._collectEPGFromDevice(channelName)
            msg="Block read:"+channelName+" size:"+str(len(xmlData))
            ml.signalMessage(ml.MSG_STATUS,msg)
            self.configuration.logInfo(msg)
            print msg
            xmlData = self._fixTV_Grab(xmlData)
            if xmlData:
                epgBlockData.append(xmlData)
        return epgBlockData    
     
             
    # Removig the category, since the data is not escaped ...
    def _fixTV_Grab(self,xmlData):
        lines = xmlData.split('\n')
        if len(lines)< 2:
            return None
        reduxList=[]
        CAT1='<category>'
        for line in lines:
            if CAT1 not in line:
                reduxList.append(line)
    
        return ''.join(reduxList)
        
'''
Recorder plugin for VLC
'''
class VLCRecorder():
    Command='cvlc'
    #TODO: different code if shell=false!   
    def getArguments(self,epgInfo,durance,filePath ):
        fileType="ts" #VLC typ
        '''
        echo 'cvlc dvb-t://frequency=530000000 :program=517 :run-time=60 --sout file/ts:/home/matze/Videos/Test2.m2t vlc://quit' | at 18:14
        vlcArgs = 'cvlc dvb-t://frequency=%s :program=%s :run-time=%s --sout file/%s:%s vlc://quit'%(freq,prog,durance,fileType,fileName)
        '''
        channelInfo = epgInfo.getChannel()
        freq = channelInfo.getFrequency()
        prog = channelInfo.getChannelID()
        #vlcArgs = 'cvlc dvb-t://frequency=%s :program=%s :run-time=%s --sout file/%s:%s vlc://quit'%(freq,prog,durance,fileType,filePath)
        vlcArgs=[]
        vlcArgs.append('cvlc')
        arg = 'dvb-t://frequency=%s'%(freq)
        vlcArgs.append(arg)
        arg = ':program=%s'%(prog)
        vlcArgs.append(arg)
        arg = ':run-time=%s'%(durance)
        vlcArgs.append(arg)
        vlcArgs.append("--sout")
        arg = "file/%s:'%s'"%(fileType,filePath) 
        vlcArgs.append(arg)
        vlcArgs.append('vlc://quit')
        return vlcArgs


'''
    Recorder plugin for tzap- lightweight and as well working as VLC!
        #tzap -r -t 60 -p -o Videos/test2.m2t zdf
        #t 60 = 60 seconds durance. Better than vlc!
'''
class TZapRecorder():
    Command='tzap'
       
    def getArguments(self,epgInfo,durance,filePath ):
        channelName = epgInfo.getChannel().getName()
        #tzapArgs = "tzap -r -p -t %s -o '%s' '%s'" %(durance,filePath,channelName)
        cmd = "tzap -r -p -t %s -o"%(durance)
        tArgs=cmd.split(" ")
        tArgs.append(filePath)
        tArgs.append(channelName)
        return tArgs

class FakeRecorder():
    Command=Config().getBinPath()+"/fakezap.sh"
        
    def getArguments(self,epgInfo,durance,filePath ):
        tArgs=[self.Command,str(durance)]
        tArgs.append(""+filePath+"")#No ' if shell=false
        return tArgs
    