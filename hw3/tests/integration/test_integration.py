import hashlib
import datetime
import unittest
import random

import api
from tests.utils import cases
from scoring import key_from_parts, get_score
from store import TarantoolStore

class TestSuite(unittest.TestCase):

    def setUp(self):
        self.context = {}
        self.headers = {}
        self.settings = {}
        self.store = TarantoolStore()

    def get_response(self, request, store=None):
        if store is None:
            store = self.store
        return api.method_handler({"body": request, "headers": self.headers}, self.context, store)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            request["token"] = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode('utf-8')).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = hashlib.sha512(msg.encode('utf-8')).hexdigest()

    def add_fake_data(self, store, ids):
        interests = ["cars", "pets", "travel", "hi-tech", "sport", "music", "books", "tv", "cinema", "geek", "otus"]
        for id in ids:
            store.set(id, random.sample(interests, 2))

    @cases([
        {"client_ids": [1, 2, 3], "date": datetime.datetime.today().strftime("%d.%m.%Y")},
        {"client_ids": [1, 2], "date": "19.07.2017"},
        {"client_ids": [0]},
    ])
    def test_store_clients_interests(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        self.add_fake_data(self.store, arguments['client_ids'])
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        self.assertEqual(len(arguments["client_ids"]), len(response))
        self.assertTrue(all(v and isinstance(v, list) and all(isinstance(i, str) for i in v)
                        for v in response.values()))
        self.assertEqual(self.context.get("nclients"), len(arguments["client_ids"]))

    @cases([
        {"client_ids": [3005001], "date": datetime.datetime.today().strftime("%d.%m.%Y")}
    ])
    def test_store_clients_interests_not_exist(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.NOT_FOUND, code, arguments)


    @cases([
        {"birthday": "01.01.2000", "first_name": "a", "last_name": "b", 'phone':79261111111}
    ])
    def test_ok_score_get_cached(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        key = key_from_parts(**arguments)
        self.store.cache_set(key, 100500, 60 * 60)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        score = response.get("score")
        self.assertTrue(isinstance(score, (int, float)) and score == 100500, arguments)
        self.assertEqual(sorted(self.context["has"]), sorted(arguments.keys()))

    @cases([
        {"birthday": "01.01.2000", "first_name": "a", "last_name": "b", 'phone':79261111111}
    ])
    def test_ok_score_get_expired(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        key = key_from_parts(**arguments)
        score_real = get_score(self.store, **arguments)
        self.store.cache_set(key, 100500, -1) # set cache value already expired
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        score = response.get("score")
        print(score, score_real)
        self.assertTrue(isinstance(score, (int, float)) and score == score_real, arguments)
        self.assertEqual(sorted(self.context["has"]), sorted(arguments.keys()))



if __name__ == "__main__":
    unittest.main()
