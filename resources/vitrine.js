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
