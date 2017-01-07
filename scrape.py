import argparse
import concurrent.futures
import json
import os
import os.path
import requests
import threading
import time
import yaml


def load_config(path):
    """Loads the configuration file from a given path."""
    return yaml.load(open(path))


def normalize_name(name):
    """Normalizes a realm or guild name for e.g. embedding in URLs."""
    return name.lower().replace(' ', '-')


class ApiClient:
    """Client for the WoW Armory API (https://dev.battle.net/io-docs).

    Handles rate limiting and provides abstractions on top of raw API
    methods.

    """

    def __init__(self, *, key, qps_limit):
        self.key = key
        self.qps_limit = qps_limit
        self.session = self._make_requests_session()

        self.quota = 0
        self.last_quota_update = 0
        self.quota_lock = threading.Lock()

    def _make_requests_session(self):
        session = requests.Session()
        session.params = {'apikey': self.key}
        session.headers.update(
            {'User-Agent': 'https://github.com/delroth/wow-guild-1p'})
        return session

    def _refill_quota(self):
        self.quota = self.qps_limit
        self.last_quota_update = time.time()

    def _acquire_quota(self):
        with self.quota_lock:
            if self.quota > 0:
                self.quota -= 1
            else:
                now = time.time()
                if now - self.last_quota_update < 1:
                    # Sleeping with the lock acquired is usually an
                    # anti-pattern, but here we really don't care because every
                    # other thread would end up going into the same sleeping
                    # pattern anyway.
                    time.sleep(now - self.last_quota_update)
                    now = time.time()
                self.last_quota_update = now
                self.quota = self.qps_limit

    def _baseurl_for_region(self, region):
        urls = {
            'eu': 'https://eu.api.battle.net/',
            'na': 'https://us.api.battle.net/',
            'kr': 'https://kr.api.battle.net/',
            'tw': 'https://tw.api.battle.net/',
            'cn': 'https://tw.api.battle.net/',
        }
        return urls.get(normalize_name(region))

    def get(self, path, *, params={}, region):
        self._acquire_quota()
        url = self._baseurl_for_region(region) + path
        result = self.session.get(url, params=params)
        return result.json()


class DictLike:
    """Small utility for data storage objects."""

    def as_dict(self):
        return NotImplemented

    def __str__(self):
        return str(self.as_dict())

    def __repr__(self):
        return repr(self.as_dict())


class RegionalInfo(DictLike):
    """Stores the regional information for a given region."""

    def __init__(self, *, region, races, classes):
        """Constructs a RegionalInfo object with pre-existing data.

        See RegionalInfo.fetch for the "public" way to construct these
        objects.

        """
        super().__init__()
        self.races = races
        self.classes = classes

    def as_dict(self):
        return {'races': self.races, 'classes': self.classes}

    @staticmethod
    def fetch(*, client, region):
        """Fetches regional info from an API client."""
        races_json = client.get('/wow/data/character/races', region=region)
        races = {}
        for race in races_json['races']:
            races[race['id']] = race['name']

        classes_json = client.get('/wow/data/character/classes', region=region)
        classes = {}
        for klass in classes_json['classes']:
            classes[klass['id']] = klass['name']

        return RegionalInfo(region=region, races=races, classes=classes)


class GuildInfo(DictLike):
    """Stores the information for a given guild."""

    def __init__(self, *, region, realm, name, mates):
        super().__init__()
        self.region = region
        self.realm = realm
        self.name = name
        self.mates = mates

    def as_dict(self):
        return {
            'region': self.region,
            'realm': self.realm,
            'name': self.name,
            'mates': {name: mate.as_dict()
                      for name, mate in self.mates.items()},
        }

    def write_to(self, file_obj):
        json.dump(self.as_dict(), file_obj)

    @staticmethod
    def fetch(*, client, region, realm, name, regional_info, config):
        guild_json = client.get(f'/wow/guild/{realm}/{name}', region=region,
                                params={'fields': 'members'})

        mates_names = []
        for member_json in guild_json['members']:
            member_json = member_json['character']
            if member_json['level'] < config['min_level']:
                print(f'    ... Skipping {member_json["name"]}-{realm}, '
                      f'level {member_json["level"]} < minimum '
                      f'{config["min_level"]}')
                continue
            mates_names.append(member_json['name'])

        # Fetch guildmates data concurrently within a guild.
        mates = {}
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(mates_names)) as pool:
            future_to_name = {
                pool.submit(Character.fetch, client=client, region=region,
                            name=mate_name, realm=realm,
                            regional_info=regional_info,
                            config=config): mate_name
                for mate_name in mates_names
            }
            for future in concurrent.futures.as_completed(future_to_name):
                mate_name = future_to_name[future]
                print(f'    ... {mate_name}-{realm}')
                mates[mate_name] = future.result()
        return GuildInfo(region=region, realm=realm, name=name, mates=mates)


class Character(DictLike):
    """Stores the information for a given character."""

    def __init__(self, *, region, realm, name, klass, race, level, ilvl,
                 progress):
        super().__init__()
        self.region = region
        self.realm = realm
        self.name = name
        self.klass = klass
        self.race = race
        self.level = level
        self.ilvl = ilvl
        self.progress = progress

    def as_dict(self):
        return {
            'region': self.region,
            'realm': self.realm,
            'name': self.name,
            'class': self.klass,
            'race': self.race,
            'level': self.level,
            'ilvl': self.ilvl,
            'progress': self.progress,
        }

    @staticmethod
    def fetch(*, client, region, realm, name, regional_info, config):
        char_json = client.get(f'/wow/character/{realm}/{name}', region=region,
                               params={'fields': 'items,progression'})

        progress = {}
        for raid in char_json['progression']['raids']:
            if raid['name'] not in config['progress_raids']:
                continue
            progress[raid['name']] = raid_progress = {}
            for difficulty in ('normal', 'heroic', 'mythic'):
                downed = 0
                total = 0
                for boss in raid['bosses']:
                    downed += (boss[f'{difficulty}Kills'] > 0)
                    total += 1
                raid_progress[difficulty] = {'downed': downed, 'total': total}

        return Character(region=region, realm=realm, name=name,
                         klass=regional_info.classes[char_json['class']],
                         race=regional_info.races[char_json['race']],
                         level=char_json['level'],
                         ilvl=char_json['items']['averageItemLevel'],
                         progress=progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(usage='Generates WoW guild one pager.')
    parser.add_argument('--config', type=str, nargs='?', default='config.yml')
    parser.add_argument('-o', '--outdir', type=str, nargs='?', default='build')
    args = parser.parse_args()

    config = load_config(args.config)
    client = ApiClient(key=config['api_key'],
                       qps_limit=config['api_qps_limit'])

    # Fetch the regional info (classes ids, achievement ids, etc.) for the
    # regions we care about.
    print('Loading regional info...')
    regional_info = {}
    for guild in config['guilds']:
        normalized_region = normalize_name(guild['region'])
        regional_info[normalized_region] = RegionalInfo.fetch(
            client=client, region=normalized_region)

    num_regions = len(regional_info)
    regions_descr = ', '.join(sorted(regional_info.keys()))
    print(f'Loaded info for {num_regions} region(s) ({regions_descr}).')

    print('Loading guild info...')
    for guild in config['guilds']:
        name, realm, region = guild['name'], guild['realm'], guild['region']
        this_regional_info = regional_info[normalize_name(region)]
        print(f'... {name}-{realm} ({region})')
        guild_info = GuildInfo.fetch(client=client,
                                     region=normalize_name(guild['region']),
                                     realm=guild['realm'],
                                     name=guild['name'],
                                     regional_info=this_regional_info,
                                     config=config)

        out_dir = os.path.join(args.outdir,
                               normalize_name(guild['region']),
                               normalize_name(guild['realm']))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(
            out_dir, normalize_name(guild['name']) + '.json')

        # Store the path in the config object to be serialized for Javascript.
        guild['path'] = out_path

        print(guild_info)
        guild_info.write_to(open(out_path, 'w'))

    del config['api_key']
    open(os.path.join(args.outdir, 'config.json'), 'w').write(
            json.dumps(config))
    print('Done!')
