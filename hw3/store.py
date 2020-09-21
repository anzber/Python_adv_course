import tarantool
import time

CONFIG = {
    'host': '127.0.0.1',
    'port': 3301,
    'simple_mode': False,
    'socket_timeout': 0.3,
    'reconnect_max_attempts': 20,
    'reconnect_delay': 0.1,
    'space': 'tester'
}

class TarantoolStore():
    def __init__(self, config=None):
        if config is None:
            config = CONFIG
        self.local_cache = {}
        self.space_name = config['space']
        if config['simple_mode']:
            self.tnt = tarantool.connect(config['host'], config['port'])
        else:
            self.tnt = tarantool.Connection(config['host'], config['port'],
                      socket_timeout=config['socket_timeout'],
                      reconnect_max_attempts=config['reconnect_max_attempts'],
                      reconnect_delay=config['reconnect_delay'])

        self.tnt.eval(f"box.schema.space.create('{self.space_name}', {{if_not_exists=true}})")
        self.tnt.eval("box.space.tester:create_index('primary', {if_not_exists=true})")

    def get(self, cid):
        res = self.tnt.select(self.space_name, cid)
        if res.data:
            return res.data[0][1]['interests']
        return res.data

    def set(self, cid, interests):
        self.tnt.delete(self.space_name, cid)
        self.tnt.insert(self.space_name, (cid, {'interests': interests}))

    def cache_get(self, key):
        if key not in self.local_cache:
            return 0
        value, expire_time = self.local_cache[key]
        if expire_time > time.time():
            del self.local_cache[key]
            return 0
        return value

    def cache_set(self, key, score, storage_time):
        """
        :param key: any value that can be an identifier for score
        :param score: score value to store
        :param storage_time: (seconds) how long the value will be available in cache
        :return:
        """
        self.local_cache[key] = (score, time.time() + storage_time)
