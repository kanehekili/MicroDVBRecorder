# -*- coding: utf-8 -*-
'''
Created on Oct 19, 2012

@author: matze
'''
import time as xtime
import subprocess
from subprocess import Popen
from Configuration import MessageListener, Config

def getRecordCommander():
    if Config.RECORD_DEVICE == Config.REC_TYPE_TZAP:
        return TZapCommand()

    if Config.RECORD_DEVICE == Config.REC_TYPE_CZAP:
        return CZapCommand()

    if Config.RECORD_DEVICE == Config.REC_TYPE_SUNDTEK:
        return MediaClientCommand()

    if Config.RECORD_DEVICE == Config.REC_TYPE_SZAP:
        return None #TODO
    
    if Config.RECORD_DEVICE == Config.REC_TYPE_VLC:
        return VLCRecorder()
    
    if Config.RECORD_DEVICE == Config.REC_TYPE_FAKE:
        return FakeRecorder()

def getGrabber(channelList,configuration):
    if Config.RECORD_DEVICE == Config.REC_TYPE_TZAP:
        return DVB_T_Grabber(channelList,configuration)

    if Config.RECORD_DEVICE == Config.REC_TYPE_VLC:
        return DVB_T_Grabber(channelList,configuration)
    
    if Config.RECORD_DEVICE == Config.REC_TYPE_CZAP:
        return DVB_C_Grabber(channelList,configuration)

    if Config.RECORD_DEVICE == Config.REC_TYPE_SUNDTEK:
        return DVBC_MediaClientGrabber(channelList,configuration)
    
    if Config.RECORD_DEVICE == Config.REC_TYPE_FAKE:
        return FAKE_Grabber(channelList,configuration)
    
    return None
    

class DVB_Grabber():
    
    MIN_DATA_THRESHOLD = 1500
    def __init__(self,channelList,configuration):
        self.channelInfos = channelList;
        self._frequencyDict=self._collectBlocks()
        self.configuration = configuration
                
    def _collectBlocks(self):
        cBlocks = {}
        for channel in self.channelInfos:
            cBlocks.setdefault(channel.getFrequency(),channel.getName())
            
        return cBlocks 
        
    '''
    collect all the info available- returns a List of xmldata
    each entry may be parsed by the EpgReader
    '''    
    def collectEPGList(self):
        epgBlockData = []
        ml = MessageListener()
        for freq,channelName in list(self._frequencyDict.items()):
            dataSize =0;
            loop=0
            msg="Scanning frequency:"+str(freq)+" ..."
            ml.signalMessage(ml.MSG_STATUS,msg)
            while dataSize < self.MIN_DATA_THRESHOLD:
                loop+=1
                xmlData = self._readEPGFromDevice(channelName)
                dataSize = len(xmlData)
                msg="Block read:"+channelName+" ["+freq+"] size:"+str(dataSize)
                ml.signalMessage(ml.MSG_STATUS,msg)
                self.configuration.logInfo(msg)
                print(msg)
                if loop > 3:
                    break;
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

    def _readEPGFromDevice(self,channelName):
        raise Exception('Implemented by subclass')        
     

class DVB_T_Grabber(DVB_Grabber):
    '''
    Grabs the data from a DVB-T device using "tzap" and tv_grab_dvb
    both applications need to have a channels.conf which should be located at ~/.tzap
    '''    

 
    def __init__(self,channelList,configuration):
        DVB_Grabber.__init__(self, channelList, configuration)
                
    #reads data from a channel and returns the XML data
    def _readEPGFromDevice(self,channelName):
        try:
            #TODO: bash that takes care of killing tzap if sth happens 
            tzapProcess = Popen(["tzap","-F","-s",channelName],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            xtime.sleep(3)
            pathToGrab = self.configuration.getBinPath()
            cmd = self.configuration.getFilePath(pathToGrab,"tv_grab_dvb")
            processResult=Popen([cmd,"-t 60","-s"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
            tzapProcess.terminate()
            tzapInfo = tzapProcess.communicate() #Closes the process, preventing a zombie
            errCode = tzapInfo[1].decode('utf8')
            tzapErrorIndex=errCode.rfind("ERROR")
            if tzapErrorIndex==-1:
                return processResult[0].decode('utf8')
        except OSError as osError:
            errorCode = "OSError - tzap or tv_grab not found:"+osError.strerror
            self.configuration.logError(errorCode)
            print(errorCode)
            raise Exception(errorCode)
        except:
            raise Exception("Unknown Device Error");
        
        #error tzap
        errorMsg = tzapInfo[1][tzapErrorIndex:]
        raise Exception("tzap: "+errorMsg)
    
class DVBC_MediaClientGrabber(DVB_Grabber): 
    def __init__(self,channelList,configuration):
        DVB_Grabber.__init__(self, channelList, configuration)
    
    def _readEPGFromDevice(self,channelName):
        #We need the id , not the channel
        pathToGrab = self.configuration.getBinPath()
        channel = self.channelForName(channelName)
        if not channel:
            self.configuration.logError("MediaClient: channel not found:"+channelName) 
            raise Exception("Channel not found");
        cmd=["/opt/bin/mediaclient","-m","DVBC","-f",channel.getFrequency(),"-M","Q"+channel.getQam(),"-S",channel.getSymbolRate()]
        try:
            czapInfo = Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
            errCode = czapInfo[1].decode('utf8')
            czapErrorIndex=errCode.rfind("ERROR")
            if czapErrorIndex != -1:
                raise Exception(errCode)

            #using the epg infos from mediaclient?
            cmd = self.configuration.getFilePath(pathToGrab,"tv_grab_dvb")
            processResult=Popen([cmd,"-t 10","-s"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
            return processResult[0].decode("latin-1");

        except OSError as osError:
            errorCode = "OSError - mediaclient or tv_grab not found:"+osError.strerror
            self.configuration.logError(errorCode)
            print(errorCode)
            raise Exception(errorCode)
        except Exception as pErr:
            raise pErr
        except:
            raise Exception("Unknown Mediaclient Error");
        
    def channelForName(self,channelName):
        for channel in self.channelInfos:
            if channel.getName()==channelName:
                return channel
            
    
         
class DVB_C_Grabber(DVB_Grabber):
    def __init__(self,channelList,configuration):
        DVB_Grabber.__init__(self, channelList, configuration)

    def _readEPGFromDevice(self,channelName):
        try:
            pathToGrab = self.configuration.getBinPath()
            czapProcess = Popen(["czap","-x","-n",channelName],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            czapInfo=czapProcess.communicate()
            errCode = czapInfo[1].decode('utf8')
            czapErrorIndex=errCode.rfind("ERROR")
            if czapErrorIndex != -1:
                raise Exception(errCode)

            #TODO either arm or not
            cmd = self.configuration.getFilePath(pathToGrab,"tv_grab_dvb")
            processResult=Popen([cmd,"-t 10","-s"],stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
            return processResult[0].decode("latin-1");
        
        except OSError as osError:
            errorCode = "OSError - tzap or tv_grab not found:"+osError.strerror
            self.configuration.logError(errorCode)
            print(errorCode)
            raise Exception(errorCode)
        except Exception as pErr:
            raise pErr
        except:
            raise Exception("Unknown Device Error");

class FAKE_Grabber(DVB_Grabber):
    '''
    Grabs the data from a fake device using files only
    '''    

 
    def __init__(self,channelList,configuration):
        DVB_Grabber.__init__(self, channelList, configuration)
                
    #reads data from a channel and returns the XML data
    def _readEPGFromDevice(self,channelName):
        #TODO read from some file...
        return ""
            
        
'''
Recorder plugin for VLC
'''
class VLCRecorder():
    Command='cvlc'
    #TODO: different code if shell=false!  TZAP impl! 
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
class TZapCommand():
    Command='tzap'
       
    def getArguments(self,epgInfo,durance,filePath ):
        channelName = epgInfo.getChannel().getName()
        #tzapArgs = "tzap -r -p -t %s -o '%s' '%s'" %(durance,filePath,channelName)
        cmd = "tzap -r -p -t %s -o"%(durance)
        tArgs=cmd.split(" ")
        tArgs.append(filePath)
        tArgs.append(channelName)
        return tArgs

class CZapCommand():
    #TODO needs bin bath for arm
    Command=Config().getBinPath()+"/czapRecord.sh"
    
    def getArguments(self,epgInfo,durance,filePath ):
        #czapRecord.sh durance filePath channel
        channelName = epgInfo.getChannel().getName()
        tArgs = [self.Command,str(durance)]
        tArgs.append(""+filePath+"")
        tArgs.append(channelName)
        return tArgs    
'''
sundtek media client recordign implementation
FW currently expects an external bash file..
mediaclient
-d /dev/dvb/adapter0/frontend0
-m DVBC
-f :erste Zahl hinter Namen
-M QAM value= QValue
-S behind: INVERSION_AUTO:
mediaclient --tsprogram last numer
-d  /dev/dvb/adapter0/dvr0 > target.m2t
durance=$1
target=$2
freq=$3
qam=$4
symbolrate=$5
progID=$6
'''

class MediaClientCommand():
    Command=Config().getBinPath()+"/mediaClientRecord.sh"
    
    def getArguments(self,epgInfo,durance,filePath ):
        channel = epgInfo.getChannel()
        tArgs = [self.Command,str(durance),channel.getFrequency(),"Q"+channel.getQam(),channel.getSymbolRate().channel.getChannelID()]
        tArgs.append(""+filePath+"")
        return tArgs    
        
    
class FakeRecorder():
    Command=Config().getBinPath()+"/fakezap.sh"
        
    def getArguments(self,epgInfo,durance,filePath ):
        tArgs=[self.Command,str(durance)]
        tArgs.append(""+filePath+"")#No ' if shell=false
        return tArgs
    