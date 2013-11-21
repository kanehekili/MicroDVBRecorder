# -*- coding: utf-8 -*-
'''
Created on Aug 10, 2012

@author: matze
'''
import re
from cgi import escape
import logging

class ChannelReader:
    '''
    reads the channel.conf and creates a channel object for each entry
    '''


    def __init__(self):
        self._fileName = None
        self._chanels = []
        
    #TODO: Killer! should stop any app if not present!    
    def readChannels(self,filename):
        try:
            channelFile = open(filename,"r+")
            result = channelFile.read()
            channelFile.close()
        except IOError:
            logging.log(logging.ERROR,"Invalid channel path")
            return None

        self._createChannels(result.splitlines())
        
    
    def _createChannels(self, stringList):
        for line in stringList:
            token=re.split(':',line)
            if len(token) < 12:
                logging.log(logging.ERROR,"channel info is corrupt")
            else:
                aChannel = Channel(token[0],token[1],token[12])
                self._chanels.append(aChannel)     

    def getChannels(self):
        return self._chanels
    
        

class Channel:
    def __init__(self,name,freq,prog):
        self._name=escape(name)
        self._frequency=freq
        self._channelID=prog
        
    def getName(self):
        return self._name
    
    #A name without /\
    def getEscapedName(self):
        matchList = re.findall('[A-z0-9]+',self._name)
        if len(matchList)==1:
            return self._name
        
        result=""
        for item in matchList:
            result=result+item+"_"
        return result[:-1]

    
    def getFrequency(self):
        return self._frequency
    
    def getChannelID(self):
        return self._channelID    
   
        