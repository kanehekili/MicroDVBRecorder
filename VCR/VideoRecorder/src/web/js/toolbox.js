//common helper methods

var getCSSRule = function(ruleClass,property){
	var searchRule='.'+ruleClass
	for (var i = 0; i < document.styleSheets.length; i++){
		var styleSheet = document.styleSheets[i];
		for (var j = 0; j < styleSheet.cssRules.length; j++){
			var rule = styleSheet.cssRules[j];
			console.log("type:"+rule.type+" txt:"+rule.selectorText);
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
	var parent = document.getElementsByClassName("yscroller")[0]
	var pTop = parent.getClientRects()[0].top
	var low= 5000;
	var candidate=null;
	for (i=0; i< dayrows.length; i++){ 
		var clientRect = dayrows[i].getClientRects()[0];
		var pos= Math.abs(clientRect.top);
		var delta = Math.abs(pos-pTop)
		if (delta < low){
			candidate=dayrows[i];
			low=delta;
		}
	}
	return candidate;
};

var removeDOMChildren = function(node){
	while (node.hasChildNodes()){
		node.removeChild(node.lastChild);
	}
};

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
