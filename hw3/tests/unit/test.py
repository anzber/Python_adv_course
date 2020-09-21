import hashlib
import datetime
import unittest
import random

import api
from tests.utils import cases


class TestSuite(unittest.TestCase):

    def setUp(self):
        self.context = {}
        self.headers = {}
        self.settings = {}
        self.store = api.MainHTTPHandler.store

    def get_response(self, request):
        return api.method_handler({"body": request, "headers": self.headers}, self.context, self.store)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            request["token"] = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode('utf-8')).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = hashlib.sha512(msg.encode('utf-8')).hexdigest()

    @cases([{}])
    def test_empty_request(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "sdd", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin", "method": "online_score", "token": "", "arguments": {}},
    ])
    def test_bad_auth(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.FORBIDDEN, code)

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score"},
        {"account": "horns&hoofs", "login": "h&f", "arguments": {}},
        {"account": "horns&hoofs", "method": "online_score", "arguments": {}},
    ])
    def test_invalid_method_request(self, request):
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue(len(response))

    @cases([
        {},
        {"phone": "79175002040"},
        {"phone": "89175002040", "email": "stupnikov@otus.ru"},
        {"phone": "79175002040", "email": "stupnikovotus.ru"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": -1},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": "1"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.1890"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "XXX"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000", "first_name": 1},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000",
         "first_name": "s", "last_name": 2},
        {"phone": "79175002040", "birthday": "01.01.2000", "first_name": "s"},
        {"email": "stupnikov@otus.ru", "gender": 1, "last_name": 2},
    ])
    def test_invalid_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    @cases([
        {"phone": "79175002040", "email": "stupnikov@otus.ru"},
        {"phone": 79175002040, "email": "stupnikov@otus.ru"},
        {"gender": 1, "birthday": "01.01.2000", "first_name": "a", "last_name": "b"},
        {"gender": 0, "birthday": "01.01.2000"},
        {"gender": 2, "birthday": "01.01.2000"},
        {"first_name": "a", "last_name": "b"},
        {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000",
         "first_name": "a", "last_name": "b"},
    ])
    def test_ok_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        score = response.get("score")
        self.assertTrue(isinstance(score, (int, float)) and score >= 0, arguments)
        self.assertEqual(sorted(self.context["has"]), sorted(arguments.keys()))

    def test_ok_score_admin_request(self):
        arguments = {"phone": "79175002040", "email": "stupnikov@otus.ru"}
        request = {"account": "horns&hoofs", "login": "admin", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        score = response.get("score")
        self.assertEqual(score, 42)

    @cases([
        {},
        {"date": "20.07.2017"},
        {"client_ids": [], "date": "20.07.2017"},
        {"client_ids": {1: 2}, "date": "20.07.2017"},
        {"client_ids": ["1", "2"], "date": "20.07.2017"},
        {"client_ids": [1, 2], "date": "XXX"},
    ])
    def test_invalid_interests_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    @cases([
        {"client_ids": [1, 2, 3], "date": datetime.datetime.today().strftime("%d.%m.%Y")},
        {"client_ids": [1, 2], "date": "19.07.2017"},
        {"client_ids": [0]},
    ])
    def test_ok_interests_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, arguments)
        self.assertEqual(len(arguments["client_ids"]), len(response))
        self.assertTrue(all(v and isinstance(v, list) and all(isinstance(i, str) for i in v)
                        for v in response.values()))
        self.assertEqual(self.context.get("nclients"), len(arguments["client_ids"]))

    @cases([
        ({"first_name": 1, "last_name": 2}, api.INVALID_REQUEST),
        ({"first_name": 1, "last_name": ''}, api.INVALID_REQUEST),
        ({"first_name": '', "last_name": ''}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin'}, api.OK)
    ])
    def test_CharField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)


    @cases([
        ({"first_name": 'vasya', "last_name": 'pupkin'}, api.OK),
        (['vasya', 'pupkin'], api.INVALID_REQUEST)
    ])
    def test_ArgumentsField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)


    @cases([
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru"}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@"}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya.otus.ru"}, api.INVALID_REQUEST)
    ])
    def test_EmailField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)

    @cases([
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233"}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "89263222233"}, api.INVALID_REQUEST),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "7926322223"}, api.INVALID_REQUEST),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "7926322223x"}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": ""}, api.OK),
    ])
    def test_PhoneField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)

    @cases([
        ({"client_ids": [1, 2], "date": "19.07.2017"}, api.OK),
        ({"client_ids": [1, 2], "date": "19.07.1017"}, api.OK),
        ({"client_ids": [1, 2], "date": ""}, api.OK),
        ({"client_ids": [1, 2], "date": "19.07.17"}, api.INVALID_REQUEST),
        ({"client_ids": [1, 2], "date": "xx.07.1980"}, api.INVALID_REQUEST)
    ])
    def test_DateField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)

    @cases([
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015"}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.1500"}, api.INVALID_REQUEST),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.8900"}, api.INVALID_REQUEST),
    ])
    def test_BirthDayField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)

    @cases([
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': 0}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': 1}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': 2}, api.OK),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': 3}, api.INVALID_REQUEST),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': "0"}, api.INVALID_REQUEST),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': "1"}, api.INVALID_REQUEST),
        ({"first_name": 'vasya', "last_name": 'pupkin', "email": "vasya@otus.ru", "phone": "79263222233",
          "birthday": "01.01.2015", 'gender': "2"}, api.INVALID_REQUEST),
    ])
    def test_GenderField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)


    @cases([
        ({"client_ids": [1, 2], "date": "19.07.2017"}, api.OK),
        ({"client_ids": [1], "date": "19.07.2017"}, api.OK),
        ({"client_ids": [1, 's'], "date": "19.07.1017"}, api.INVALID_REQUEST),
        ({"client_ids": [], "date": "19.07.1017"}, api.INVALID_REQUEST),
        ({"client_ids": [''], "date": "19.07.1017"}, api.INVALID_REQUEST)
    ])
    def test_ClientIDsField(self, arguments, expected_code):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(expected_code, code)


if __name__ == "__main__":
    unittest.main()
