//common helper methods

var getCSSRule = function(ruleClass,property){
	var searchRule='.'+ruleClass
	for (var i = 0; i < document.styleSheets.length; i++){
		var styleSheet = document.styleSheets[i];
		for (var j = 0; j < styleSheet.cssRules.length; j++){
			var rule = styleSheet.cssRules[j];
			//console.log("type:"+rule.type+" txt:"+rule.selectorText);
			if (rule.selectorText==searchRule){
				// Do something with rule.style.width
				return rule.style.backgroundColor;
			}
		}
	}
	return null;	
};

var confirmBox=function(prompt){
	var result=confirm(prompt);
	return result;
};

var nearestDayRow = function(){
	var dayrows= document.getElementsByClassName("dayrow");
	var parent = document.getElementsByClassName("yscroller")[0];
	var pTop = parent.getClientRects()[0].top;
	var low= 5000;
	var candidate=null;
	for (i=0; i< dayrows.length; i++){ 
		var clientRect = dayrows[i].getClientRects()[0];
		var pos= Math.abs(clientRect.top);
		var delta = Math.abs(pos-pTop);
		if (delta < low){
			candidate=dayrows[i];
			low=delta;
		}
	}
	return candidate;
};

var getDayRowByName = function(theName){
	var dayrows= document.getElementsByClassName("dayrow");
	for (i=0; i< dayrows.length; i++){ 
		if (dayrows[i].innerHTML == theName)
			return dayrows[i];
	}
	return dayrows[dayrows.length-1];
}

var removeDOMChildren = function(node){
	while (node.hasChildNodes()){
		node.removeChild(node.lastChild);
	}
};

var isOverlapping = function (dom1,dom2) {
	var rect1 = dom1.getBoundingClientRect();
	var rect2 = dom2.getBoundingClientRect();
	var isApart = (rect1.right < rect2.left || 
                rect1.left > rect2.right || 
                rect1.bottom < rect2.top || 
                rect1.top > rect2.bottom);
    return !isApart;
}

var getChildByClass = function(node,className){
	children= node.childNodes;
	for (i=0; i< children.length; i++){ 
		if (children[i].className==className){
			return children[i];
		}
	}
	return null;
}

var showStatus =function(message){
	var status= document.getElementById("footer");
	status.textContent=message;
    console.log(message);
};

var removeClassName = function(node, aClassname) {
	var replacement=" "+aClassname;
	var test=node.className;
	node.className=node.className.replace(replacement,"");
}

var addClassName = function(node, aClassname) {
	var replacement=" "+aClassname;
	this.removeClassName(node,aClassname);
	var aClassName=node.className+replacement;
	node.className=aClassName;
}

var secondStringToMinutes = function(seconds){
	return parseInt(seconds)/60;
}

var minuteStringToSeconds = function(minutes){
	return parseInt(minutes)*60;
}

var showMessageInProgrammArea = function(message, mainDOM) {
	var row = document.createElement("div");
	row.className="nodatarow"; //should be error row or icon or so.
	row.innerHTML=message;
	mainDOM.appendChild(row);
}

/*Touch support
* TODO activation by touching long - if div not present on touch end - ignore.
*/

function TouchHandler(aDiv) {
	this.domObject = aDiv;
	this.lastTouch=0;
	this.startX=0;
	this.startY=0;
	this.touchMode=0;
    this.markHover=false;
    //hooks for gestures
	this.runOnDoubleTab=null;
    this.runOnTab=null;
	this.runOnLongTouch=null;
    this.runOnHorizontalSwipe=null;
    //hooks for the events -execute specific code
    this.connectOnTouchStart=null;
    this.connectOnTouchMove=null;
    this.connectOnTouchEnd=null;
      
	this._connectToTouch();

    
}
TouchHandler.MODE_DBLETAB=0xA1;
TouchHandler.MODE_LONGTAB=0xA2;
TouchHandler.MODE_SWIPEY=0xA3;
TouchHandler.MODE_TAB=0xA4;
TouchHandler.MODE_NONE=0x0;

TouchHandler.prototype.showHover = function(aBoolean){
    this.markHover=aBoolean;
}

TouchHandler.prototype.onDoubleTab = function(context,aFunction){
	this.runOnDoubleTab=aFunction.bind(context);
};

TouchHandler.prototype.onTab = function(context,aFunction){
	this.runOnTab=aFunction.bind(context);
};

TouchHandler.prototype.onLongTouch = function(context,aFunction){
	this.runOnLongTouch=aFunction.bind(context);
};

TouchHandler.prototype.onHorizontalSwipe = function(context,aFunction){
	this.runOnHorizontalSwipe=aFunction.bind(context);
};

TouchHandler.prototype.onTouchStart = function(context,aFunction){
    this.connectOnTouchStart=aFunction.bind(context);
};

TouchHandler.prototype.onTouchMove = function(context,aFunction){
    this.connectOnTouchMove=aFunction.bind(context);
};

TouchHandler.prototype.onTouchEnd = function(context,aFunction){
    this.connectOnTouchEnd=aFunction.bind(context);
};


TouchHandler.prototype._setLastTouch = function (event) {
    this.lastTouch=event.changedTouches[0];
    this.lastTouch.timeStamp=event.timeStamp;
}
TouchHandler.prototype._connectToTouch = function(){
	this.domObject.addEventListener("touchstart",this.handleTouchStart.bind(this),false);
	this.domObject.addEventListener("touchmove",this.handleTouchMove.bind(this),true);
	this.domObject.addEventListener("touchend",this.handleTouchEnd.bind(this),false);
    this.domObject.addEventListener("touchcancel",this.handleTouchCanx.bind(this),false);
    //this.domObject.addEventListener("touchleave",this.handleTouchLeave.bind(this),false);
	this.domObject.addEventListener("contextmenu",this.handleContextMenu.bind(this),false);
};
//thru "bind" context is this, not the dom
TouchHandler.prototype.handleTouchStart= function(event){
	var touch=event.changedTouches[0];
	this.startX=touch.pageX;
	this.startY=touch.pageY;
    if (this.markHover)
	    addClassName(this.domObject,"InfoRowHover");
	var currHit = event.timeStamp;
    var delta = 1e5;
    if (this.lastTouch!=null)
	    delta = currHit - this.lastTouch.timeStamp;
	if (delta <350){
		this.touchMode=TouchHandler.MODE_DBLETAB;
	} else {
		this.touchMode=TouchHandler.MODE_TAB;
 	}

	this._setLastTouch(event);	
    if (this.connectOnTouchStart !=null)
        this.connectOnTouchStart(touch);
};

TouchHandler.prototype.handleContextMenu= function(event){
    this.touchMode=TouchHandler.MODE_LONGTAB;
    removeClassName(this.domObject,"InfoRowHover");
	addClassName(this.domObject,"InfoRowHit");
    this.touchMode=TouchHandler.MODE_LONGTAB;
}

//Android hook- does not really show moves!
TouchHandler.prototype.handleTouchCanx= function(event){
	removeClassName(this.domObject,"InfoRowHover");
	removeClassName(this.domObject,"InfoRowHit");
    this.lastTouch=null;
    
};

TouchHandler.prototype.handleTouchLeave= function(event){
     //Stub
};

TouchHandler.prototype.handleTouchMove= function(event){
	var touch=event.changedTouches[0];
    var dx = Math.abs(touch.pageX-this.startX);
    var dy = Math.abs(touch.pageY-this.startY);
    touch.touchMode=this.touchMode;
    if (dx>dy){
        event.preventDefault();//needed if we want a horizonal swipe - otherwise canx is activated
    }
    
    if (this.connectOnTouchMove !=null && this.connectOnTouchMove(touch)){
           event.preventDefault();//This prevents scrolling in a list, but fires more touch events
     }


	if (this.touchMode == TouchHandler.MODE_SWIPEY && !isTouched(this.domObject,touch.pageX,touch.pageY)){
    	removeClassName(this.domObject,"InfoRowHover");
		removeClassName(this.domObject,"InfoRowHit");
        return;
	}


    //make the distance dependend on the node size
    if (this.runOnHorizontalSwipe != null) {
       var box = this.domObject.getBoundingClientRect()
        if (dx > box.width/3){
            this.touchMode=TouchHandler.MODE_SWIPEY;
            addClassName(this.domObject,"InfoRowHit");
        }
    }
    this._setLastTouch(event);		
    
};

/*
TouchHandler.prototype.canxTimer = function() {
    if (this.touchTimer != null)
        window.clearTimeout(this.touchTimer);
    this.touchTimer = null;
}
*/

TouchHandler.prototype.handleTouchEnd= function(event){

	removeClassName(this.domObject,"InfoRowHover");
	removeClassName(this.domObject,"InfoRowHit");
	var touch=event.changedTouches[0];
    if (this.connectOnTouchEnd !=null)
       this.connectOnTouchEnd(touch);
       
	if (!isTouched(this.domObject,touch.pageX,touch.pageY)){
 		return;
	}
	
	if (this.touchMode==TouchHandler.MODE_DBLETAB){
		if (this.runOnDoubleTab!=null)
			this.runOnDoubleTab(touch);
	}else if (this.touchMode==TouchHandler.MODE_LONGTAB){
		if (this.runOnLongTouch != null)
			this.runOnLongTouch(touch);
	}else if (this.touchMode==TouchHandler.MODE_SWIPEY){
		if (this.runOnHorizontalSwipe != null)
			this.runOnHorizontalSwipe(touch);
	}else if (this.touchMode==TouchHandler.MODE_TAB){
    	var currHit = event.timeStamp;
	    var delta = currHit - this.lastTouch.timeStamp;
		if (this.runOnTab != null && delta>200)
			this.runOnTab(touch);
	}
	this.touchMode=TouchHandler.MODE_NONE;
    this.lastTouch=null;
	//event.preventDefault();
};

//Context window
function timerHandleLongTouch(touchHandler){
	removeClassName(touchHandler.domObject,"InfoRowHover");
	addClassName(touchHandler.domObject,"InfoRowHit");
	touchHandler.touchMode=TouchHandler.MODE_LONGTAB;
}

function isTouchedX(node,touchX){
	var targetRect = node.getBoundingClientRect();
	var fitX = targetRect.left < touchX && touchX < targetRect.right;
	return fitX;
};

function isTouchedY(node,touchY){
	var targetRect = node.getBoundingClientRect();
    var fitY = targetRect.top < touchY && touchY < targetRect.bottom;
	return fitY;
};

function isTouched(node,touchX,touchY){
	var targetRect = node.getBoundingClientRect();
	var fitX = targetRect.left < touchX && touchX < targetRect.right;
	var fitY = targetRect.top < touchY && touchY < targetRect.bottom;
	return fitX & fitY;
	
}

function FakeDragEvent (aTarget) {
	this.target=aTarget;
	this.dataTransfer=new FakeDataTransfer(0);
}
FakeDragEvent.prototype.preventDefault = function(){
};

FakeDragEvent.prototype.setDomId= function(id){
	this.dataTransfer.id = id;
};


function FakeDataTransfer(aDomid) {
	this.id = aDomid;
};
FakeDataTransfer.prototype.getData =function(aString){
	return this.id;
};

function is_touch_device() {
  return 'ontouchstart' in window;
};

function getScreenWidth(){
  return window.screen.availWidth;
}

function getScreenHeight(){
  return window.screen.availHeight;
}

function eventFire(node, etype){
  if (node.fireEvent) {
    node.fireEvent('on' + etype);
  } else {
    var evObj = document.createEvent('Events');
    evObj.initEvent(etype, true, false);
    node.dispatchEvent(evObj);
  }
}

function getNodeUnderPointer(px,py){
    return document.elementFromPoint(px, py);
}

function resetTouchDragItem(){
    touchDragItem.style.left = 0+'px';
    touchDragItem.style.top = 0+'px';
    touchDragItem.innerHTML = "";
}
