import six
from jawa.classloader import ClassLoader

from .topping import Topping


class StatsTopping(Topping):
    """Gets all statistics and statistic related strings."""

    PROVIDES = ['stats.statistics', 'stats.achievements']

    DEPENDS = ['language']

    @staticmethod
    def act(aggregate, classloader: ClassLoader):
        stats = aggregate.setdefault('stats', {})
        if 'stat' in aggregate['language']:
            stat_lang = aggregate['language']['stat']

            for sk, sv in six.iteritems(stat_lang):
                item = stats.setdefault(sk, {})
                item['desc'] = sv

        achievements = aggregate.setdefault('achievements', {})
        if 'achievement' in aggregate['language']:
            achievement_lang = aggregate['language']['achievement']

            for ak, av in six.iteritems(achievement_lang):
                real_name = ak[:-5] if ak.endswith('.desc') else ak
                item = achievements.setdefault(real_name, {})
                if ak.endswith('.desc'):
                    item['desc'] = av
                else:
                    item['name'] = av
