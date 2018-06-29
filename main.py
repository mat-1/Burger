from html import escape
from browser import document, window, html, ajax, webworker, console
import traceback
import json
import sys
worker = None
active_future = None

def update_result(*args, **kwargs):
    left = document.select("#version-main select")[0].value
    right = document.select("#version-diff select")[0].value
    document.select("#version-main span")[0].textContent = left
    document.select("#version-diff span")[0].textContent = right

    document.getElementById("vitrine").innerHTML = '''
    <h2>Working...</h2><div class="entry">
    <h3><label for="vitrine-progress" id="vitrine-progress-label">Loading burger JSONs...</label></h3>
    <progress id="vitrine-progress"></progress>
    </div>
    '''
    progress_label = document.getElementById("vitrine-progress-label")
    progress_bar = document.getElementById("vitrine-progress") # starts in indeterminate state

    def updates_vitrine(f):
        global worker

        if not worker:
            progress_label.textContent = "Starting worker..."
            def progress_handler(message_name, message, src):
                data = message.data.to_dict()
                print("Progress update:", data)

                progress_label.textContent = data['desc']
                if 'value' in data:
                    progress_bar.max = data['max']
                    progress_bar.value = data['value']
                else:
                    progress_bar.removeAttribute('max')
                    progress_bar.removeAttribute('value')

            # Ugly hack to get an absolute URL from a relative one
            # https://stackoverflow.com/a/34020609/3991344
            url = html.A(href='worker.py').href
            worker = webworker.WorkerParent(url, sys.path)
            worker.bind_message('progress', progress_handler)

        """
        Decorator to update vitrine based on the future returned by the given method,
        using a webworker.
        """
        def method(*args, **kwargs):
            global active_future
            if active_future is not None:
                active_future.cancel()
                active_future = None

            active_future = f(*args, **kwargs)
            def callback(future):
                active_future.cancel()
                active_future = None
                try:
                    document.getElementById("vitrine").innerHTML = future.result().data.to_dict()['result']
                except CancelledError:
                    pass
                except:
                    traceback.print_exc()
                    document.getElementById("vitrine").innerHTML = '<div class="entry"><h3>Error callback</h3><pre>' + escape(traceback.format_exc()) + '</pre></div>'
            active_future.add_done_callback(callback)

        return method

    @updates_vitrine
    def single(request):
        print("Preparing vitrine worker")
        data = request.responseText
        return worker.post_message(webworker.Message('vitrine', {'data': data}), want_reply=True)

    class BothCallback:
        def __init__(self):
            self.main = None
            self.diff = None

        def onmain(self, request):
            self.main = request.responseText
            if self.main is not None and self.diff is not None:
                self.done()

        def ondiff(self, request):
            self.diff = request.responseText
            if self.main is not None and self.diff is not None:
                self.done()

        @updates_vitrine
        def done(self):
            print("Preparing hamburglar worker")
            return worker.post_message(webworker.Message('hamburglar', {'main': self.main, 'diff': self.diff}), want_reply=True)

    if left == "None" and right == "None":
        #window.location = "about"
        return
    elif left == "None":
        req = ajax.ajax()
        req.open("GET", "https://pokechu22.github.io/Burger/" + right + ".json", True)
        req.bind("complete", single)
        req.send()
    elif right == "None":
        req = ajax.ajax()
        req.open("GET", "https://pokechu22.github.io/Burger/" + left + ".json", True)
        req.bind("complete", single)
        req.send()
    else:
        callback = BothCallback()
        req = ajax.ajax()
        req.open("GET", "https://pokechu22.github.io/Burger/" + left + ".json", True)
        req.bind("complete", callback.onmain)
        req.send()
        req = ajax.ajax()
        req.open("GET", "https://pokechu22.github.io/Burger/" + right + ".json", True)
        req.bind("complete", callback.ondiff)
        req.send()

document.select("#version-main select")[0].bind("change", update_result)
document.select("#version-diff select")[0].bind("change", update_result)

# Tooltips
""" NYI
document.select("body")[0] <= html.DIV(id="tooltip")
$(document).mousemove(function(e) {
    $("#tooltip").css({
        top: (e.pageY - 30) + "px",
        left: (e.pageX + 20) + "px"
    });
});

$(".item, .texture, .craftitem").on("mouseover", function() {
    $("#tooltip").show().html(this.title)
}).on("mouseout", function() {
    $("#tooltip").hide()
});
"""

def initalize(request):
    versions = json.loads(request.responseText)

    if len(versions) < 1:
        raise Exception("No versions are available")

    # https://stackoverflow.com/a/901144/3991344 (bleh)
    def getParameterByName(name):
        regex = window.RegExp.new("[?&]" + name + "(=([^&#]*)|&|#|$)");
        results = regex.exec(window.location.href);
        if not results or not results[2]:
            return None
        return window.decodeURIComponent(results[2].replace('+', " "))

    main = getParameterByName("main")
    if main not in versions:
        main = versions[0]

    diff = getParameterByName("diff")
    if diff not in versions:
        diff = "None"

    for ver in versions:
        document.select("#version-main select")[0] <= html.OPTION(ver, value=ver)
        document.select("#version-diff select")[0] <= html.OPTION(ver, value=ver)

    document.select("#version-main select")[0].disabled = False
    document.select("#version-main select")[0].value = main
    document.select("#version-diff select")[0].disabled = False
    document.select("#version-diff select")[0].value = diff

    update_result()

req = ajax.ajax()
req.open("GET", "https://pokechu22.github.io/Burger/versions.json", True)
req.bind("complete", initalize)
req.send()