$(function() {
	$("body").append('<div id="tooltip"></div>');
	
	$(document).mousemove(function(e) {
		$("#tooltip").css({
			top: (e.pageY - 30) + "px",
			left: (e.pageX + 20) + "px"
		});
	});
	
	$(".item, .texture, .craftitem").live("mouseover", function() {
		$("#tooltip").show().html(this.title)
	}).live("mouseout", function() {
		$("#tooltip").hide()
	});
});

playSound = function(element) {
	var link = element.dataset.link;
	var pitch = (element.dataset.hasOwnProperty("pitch")) ? element.dataset.pitch : 1;
	var volume = (element.dataset.hasOwnProperty("volume")) ? element.dataset.volume : 1;
	// HTML doesn't like extreme volumes, but Minecraft does use them (for 3D audio)
	if (volume < 0) {
		volume = 0;
	} else if (volume > 1) {
		volume = 1;
	}

	var audioElement = document.createElement("audio");
	var sourceElement = document.createElement("source");
	sourceElement.src = link;
	sourceElement.type = "audio/ogg";
	audioElement.appendChild(sourceElement);
	audioElement.autoplay = true;
	audioElement.controls = true;
	audioElement.volume = volume;
	// Note: normally tries to adjust pitch to be constant.
	// See https://wiki.developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/playbackRate
	// However, there is a nonstandard preservesPitch/mozPreservesPitch/webkitPreservesPitch property that can disable that
	audioElement.playbackRate = pitch;
	if ("preservesPitch" in audioElement) {
		audioElement.preservesPitch = false;
	} else if ("mozPreservesPitch" in audioElement) {
		audioElement.mozPreservesPitch = false;
	} else if ("webkitPreservesPitch" in audioElement) {
		audioElement.webkitPreservesPitch = false;
	} else {
		if (!window.warnedAboutPitch) {
			alert("Your browser does not support disabling pitch rescaling.  Try a different browser, such as Firefox.");
			window.warnedAboutPitch = true;
		}
	}

	// Replace button with the audio tag
	element.parentElement.appendChild(audioElement);
	element.parentElement.removeChild(element);
}
