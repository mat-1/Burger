# Based on vitrine.py and hamburglar.py

from browser import document, window, html, ajax
import json
import traceback
import hamburglar_main
import vitrine_main

def hamburglar(main, diff):
    def import_toppings():
        # Silly hardcoded thing; we can't go through all files here
        from hamburglar.toppings.achivements import AchivementsTopping
        from hamburglar.toppings.packets import PacketsTopping
        from hamburglar.toppings.recipes import RecipesTopping
        from hamburglar.toppings.stats import StatsTopping
        from hamburglar.toppings.tags import TagsTopping
        from hamburglar.toppings.version import VersionTopping
        from hamburglar.toppings.biomes import BiomesTopping
        from hamburglar.toppings.blocks import BlocksTopping
        from hamburglar.toppings.entities import EntitiesTopping
        from hamburglar.toppings.entities import ObjectsTopping
        from hamburglar.toppings.items import ItemsTopping
        from hamburglar.toppings.sounds import SoundsTopping
        from hamburglar.toppings.tileentities import TileEntitiesTopping
        from hamburglar.toppings.language import LanguageTopping

        return (AchivementsTopping, PacketsTopping, RecipesTopping, StatsTopping, TagsTopping, VersionTopping, BiomesTopping, BlocksTopping, EntitiesTopping, ObjectsTopping, ItemsTopping, SoundsTopping, TileEntitiesTopping, LanguageTopping)

    toppings = import_toppings()

    return hamburglar_main.compare(toppings, main[0], diff[0])

def vitrine(data):
    def import_toppings():
        # Silly hardcoded thing
        from vitrine.toppings.achievements import AchievementsTopping
        from vitrine.toppings.biomes import BiomesTopping
        from vitrine.toppings.entities import EntitiesTopping
        from vitrine.toppings.language import LanguageTopping
        from vitrine.toppings.objects import ObjectsTopping
        from vitrine.toppings.packets import PacketsTopping
        from vitrine.toppings.recipes import RecipesTopping
        from vitrine.toppings.sounds import SoundsTopping
        from vitrine.toppings.stats import StatsTopping
        from vitrine.toppings.tags import TagsTopping
        from vitrine.toppings.tileentities import TileEntities
        from vitrine.toppings.versions import VersionsTopping
        from vitrine.toppings.blocks import BlocksTopping
        from vitrine.toppings.items import ItemsTopping

        return (AchievementsTopping, BiomesTopping, EntitiesTopping, LanguageTopping, ObjectsTopping, PacketsTopping, RecipesTopping, SoundsTopping, StatsTopping, TagsTopping, TileEntities, VersionsTopping, BlocksTopping, ItemsTopping)

    toppings = import_toppings()

    return vitrine_main.generate_html(toppings, data, wiki=None)

def update_result(*args, **kwargs):
    left = document.select("#version-main select")[0].value
    right = document.select("#version-diff select")[0].value
    document.select("#version-main span")[0].textContent = left
    document.select("#version-diff span")[0].textContent = right

    def updates_vitrine(f):
        def method(*args, **kwargs):
            try:
                content = f(*args, **kwargs)
                document.getElementById("vitrine").innerHTML = content
            except:
                import html
                document.getElementById("vitrine").innerHTML = '<div class="entry"><h3>Error</h3><pre>' + html.escape(traceback.format_exc()) + '</pre></div>'
                traceback.print_exc()

        return method

    @updates_vitrine
    def single(request):
        data = json.loads(request.responseText)
        return vitrine(data)

    class BothCallback:
        def __init__(self):
            self.main = None
            self.diff = None

        def onmain(self, request):
            self.main = json.loads(request.responseText)
            if self.main is not None and self.diff is not None:
                self.done()

        def ondiff(self, request):
            self.diff = json.loads(request.responseText)
            if self.main is not None and self.diff is not None:
                self.done()

        @updates_vitrine
        def done(self):
            combined = hamburglar(self.main, self.diff)
            return vitrine(combined)

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