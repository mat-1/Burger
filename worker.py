from browser.webworker import current_worker, Message
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

def vitrine_worker(message):
    print("vitrine_worker:", message)
    result = vitrine(message.data)
    print("Done!")
    current_worker.post_reply(message, Message('vitrine', result))

def hamburglar_worker(message):
    print("hamburglar_worker:", message)
    combined = hamburglar(message.data['main'], message.data['diff'])
    print("Halfway done")
    result = vitrine(combined)
    print("Done")
    current_worker.post_reply(message, Message('hamburglar', result))

current_worker.bind_message('vitrine', vitrine_worker)
current_worker.bind_message('hamburglar', hamburglar_worker)
current_worker.exec()