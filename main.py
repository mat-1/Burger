# Based on vitrine.py and hamburglar.py

from browser import document, window, html, ajax
import json
import traceback

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
    versions = [main[0], diff[0]]

    # Compare versions
    aggregate = {}

    for topping in toppings:
        if topping.KEY == None:
            continue
        keys = topping.KEY.split(".")
        obj1 = versions[0]
        obj2 = versions[1]
        target = aggregate
        skip = False
        for key in keys:
            if not (key in obj1 and key in obj2):
                skip = True
                break
            obj1 = obj1[key]
            obj2 = obj2[key]
        if skip:
            continue
        for key in keys[:-1]:
            if not key in target:
                target[key] = {}
            target = target[key]

        print(topping)
        target[keys[-1]] = topping().filter(obj1, obj2)

    return aggregate

def vitrine(data):
    def import_toppings():
        # Silly hardcoded thing
        from vitrine.toppings.achievements import AchievementsTopping
        from vitrine.toppings.biomes import BiomesTopping
        import vitrine.toppings.entities #EntitiessTopping
        from vitrine.toppings.language import LanguageTopping
        import vitrine.toppings.objects #EntitiessTopping
        from vitrine.toppings.packets import PacketsTopping
        from vitrine.toppings.recipes import RecipesTopping
        from vitrine.toppings.sounds import SoundsTopping
        from vitrine.toppings.stats import StatsTopping
        from vitrine.toppings.tags import TagsTopping
        from vitrine.toppings.tileentities import TileEntities
        from vitrine.toppings.versions import VersionsTopping
        from vitrine.toppings.blocks import BlocksTopping
        from vitrine.toppings.items import ItemsTopping

        return (AchievementsTopping, BiomesTopping, vitrine.toppings.entities.EntitiessTopping, LanguageTopping, vitrine.toppings.objects.EntitiessTopping, PacketsTopping, RecipesTopping, SoundsTopping, StatsTopping, TagsTopping, TileEntities, VersionsTopping, BlocksTopping, ItemsTopping)

    toppings = import_toppings()

    diff = not isinstance(data, list)
    if not diff:
        data = data[0]

    wiki = None

    # Generate HTML
    aggregate = [] # changed for performance
    for topping in sorted(toppings, key=lambda x: -x.PRIORITY):
        if topping.KEY == None:
            continue

        keys = topping.KEY.split(".")
        obj = data
        skip = False
        for key in keys:
            if key not in obj:
                skip = True
                break
            obj = obj[key]
        if skip:
            continue

        try:
            print(topping)
            aggregate.append(str(topping(obj, data, diff, wiki)))
        except:
            aggregate.append('<h2>%s</h2><div class="entry"><h3>Error</h3><pre>%s</pre></div>' % (topping.NAME, traceback.format_exc()))
            traceback.print_exc()

    return "".join(aggregate)

def update_result(*args, **kwargs):
    left = document.select("#version-main select")[0].value
    right = document.select("#version-diff select")[0].value
    document.select("#version-main span")[0].textContent = left
    document.select("#version-diff span")[0].textContent = right

    def single(request):
        data = json.loads(request.responseText)
        try:
            content = vitrine(data)
            document.getElementById("vitrine").innerHTML = content
        except:
            document.getElementById("vitrine").innerHTML = '<div class="entry"><h3>Error</h3><pre>' + traceback.format_exc() + '</pre></div>'
            traceback.print_exc()

    def both1(request):
        main = json.loads(request.responseText)
        def both2(request2):
            diff = json.loads(request2.responseText)
            combined = hamburglar(main, diff)

            try:
                content = vitrine(combined)
                document.getElementById("vitrine").innerHTML = content
            except:
                document.getElementById("vitrine").innerHTML = '<div class="entry"><h3>Error</h3><pre>' + traceback.format_exc() + '</pre></div>'
                traceback.print_exc()

        req = ajax.ajax()
        req.open("GET", "https://pokechu22.github.io/Burger/" + right + ".json", True)
        req.bind("complete", both2)
        req.send()

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
        req = ajax.ajax()
        req.open("GET", "https://pokechu22.github.io/Burger/" + left + ".json", True)
        req.bind("complete", both1)
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