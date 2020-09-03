#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Homework 3
Scoring API
"""

import json
import datetime
import logging
import hashlib
import uuid
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from abc import ABCMeta, abstractmethod
from dateutil.relativedelta import relativedelta
from scoring import get_score, get_interests

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class BaseField(metaclass=ABCMeta):
    """
    Base half-abstract class for fields.
    Child classes should implement check_validity
    """
    def __init__(self, required, nullable=False):
        self.required = required
        self.nullable = nullable

    @abstractmethod
    def check_validity(self, value):
        """
        Abstract method for check if field is valid
        """

class CharField(BaseField):
    """
    Char field
    """
    def check_validity(self, value):
        """
        Check validity condition - value is string
        """
        return isinstance(value, str)


class ArgumentsField(BaseField):
    """
    Arguments Field
    """
    def check_validity(self, value):
        """
        Check validity condition - value is dict
        """
        return isinstance(value, dict)


class EmailField(CharField):
    """
    Email Field
    """
    def check_validity(self, value):
        """
        Check validity condition - value is string and has @
        """
        return isinstance(value, str) and ('@' in value)


class PhoneField(BaseField):
    """
    Phone Field
    """
    def check_validity(self, value):
        """
        Check validity condition - starts with 7, has 11 symbols
        Can be empty
        """
        if not value:
            return True
        if isinstance(value, (int, str)):
            return len(str(value)) == 11 and (str(value)[0] == '7')


class DateField(BaseField):
    """
    Date Field
    """
    def check_validity(self, value):
        """
        Check validity condition - any valid date with format dd.mm.yyyy
        """
        if isinstance(value, str):
            try:
                datetime.datetime.strptime(value, "%d.%m.%Y")
                return True
            except:
                pass
        return False


class BirthDayField(BaseField):
    """
    Birthday Field
    """
    def check_validity(self, value):
        """
        Check validity condition - any valid date with format dd.mm.yyyy
        No more than 70 years ago
        """
        if isinstance(value, str):
            try:
                difference_in_years = relativedelta(datetime.datetime.now(),
                                                    datetime.datetime.strptime(value, "%d.%m.%Y")).years
                return difference_in_years <= 70
            except:
                pass
        return False


class GenderField(BaseField):
    """
    Gender Field
    """
    def check_validity(self, value):
        """
        Check validity condition - one of fixed set
        """
        return value in [UNKNOWN, MALE, FEMALE]


class ClientIDsField(BaseField):
    """
    Client IDs Field
    """
    def check_validity(self, value):
        """
        Check validity condition - list of integers
        """
        if isinstance(value, list) and value:
            is_valid = True
            for client_id in value:
                if not isinstance(client_id, int):
                    is_valid = False
                    break
            return is_valid
        return False


class BaseMethod():
    """
    Parent class for parsing and validating json requests
    """
    def __init__(self, request):
        self.wrong_arguments = []
        self.missed_required = []
        self.parameters = {}
        self.wrong_fields = []
        for field, value in request.items():
            if field in self.__class__.__dict__:
                setattr(self, field, value)
                self.parameters[field] = value
            else:
                self.wrong_arguments.append(field)
        for field_name, field in self.__class__.__dict__.items():
            if not isinstance(field, BaseField):
                continue
            # check if param in request
            field_value = getattr(self, field_name)
            if isinstance(field_value, BaseField):
                if field.required:
                    self.missed_required.append(field_name)
            else:
                if not field.check_validity(field_value):
                    self.wrong_fields.append(field_name)

    def check_request_validity(self):
        """
        Common validity checking
        """
        if self.wrong_arguments:
            return "Wrong arguments: " + ", ".join(self.wrong_arguments), INVALID_REQUEST
        if self.missed_required:
            return "Missed required arguments: " + ", ".join(self.missed_required), INVALID_REQUEST
        if self.wrong_fields:
            return "Wrong field values: " + ", ".join(self.wrong_fields), INVALID_REQUEST
        return '', 0


class ClientsInterestsRequest(BaseMethod):
    """
    ClientsInterests request structure
    """
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(BaseMethod):
    """
    OnlineScore request structure
    """
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)


    def check_request_validity(self):
        """
        Checking if at least two fields present
        """

        def check_valid_pair(field1, field2):
            """
            Check if given pair of fields is present
            """
            if isinstance(field1, BaseField) or isinstance(field2, BaseField):
                return False
            return not ((field1 is None) or (field2 is None))

        errors, error_code = super().check_request_validity()
        if error_code:
            return errors, error_code
        valid_pairs = [('phone', 'email'), ('first_name', 'last_name'), ('gender', 'birthday')]

        has_valid_pair = False
        for field1, field2 in valid_pairs:
            if check_valid_pair(getattr(self, field1), getattr(self, field2)):
                has_valid_pair = True
                break
        if not has_valid_pair:
            return 'No valid field pair presented', INVALID_REQUEST
        return '', 0


class MethodRequest(BaseMethod):
    """
    Parse and check validity of request
    """
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        """
        Check if user is admin
        """
        return self.login == ADMIN_LOGIN


def check_auth(request):
    """
    Check auth token is valid
    """
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT) \
                                .encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request.account + request.login + SALT)\
                                .encode('utf-8')).hexdigest()
    if digest == request.token:
        return True
    return False


def online_score_handler(method_request, ctx, store):
    """
    Process onlinescore request and return response
    """
    online_score_request = OnlineScoreRequest(method_request.arguments)

    error_message, error_code = online_score_request.check_request_validity()
    if error_message:
        return error_message, error_code
    ctx['has'] = [key for key in online_score_request.parameters]
    if method_request.is_admin:
        return {'score': 42}, OK
    return {'score': get_score(store, **online_score_request.parameters)}, OK


def clients_interests_handler(method_request, ctx, store):
    """
    Process clientsinterests request and return response
    """
    clients_interests_request = ClientsInterestsRequest(method_request.arguments)
    error_message, error_code = clients_interests_request.check_request_validity()
    if error_message:
        return error_message, error_code
    ctx['nclients'] = len(clients_interests_request.client_ids)
    return {str(id): get_interests(store, id) for id in clients_interests_request.client_ids}, OK


def method_handler(request, ctx, store):
    """
    Common request processing and routing to specific handler
    """
    method_request = MethodRequest(request['body'])
    error_message, error_code = method_request.check_request_validity()
    if error_message:
        return error_message, error_code

    if not check_auth(method_request):
        return ERRORS[FORBIDDEN], FORBIDDEN

    method_router = {
        "online_score": online_score_handler,
        "clients_interests": clients_interests_handler
    }
    if method_request.method in method_router:
        return method_router[method_request.method](method_request, ctx, store)
    return ERRORS[NOT_FOUND], NOT_FOUND


class MainHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler
    """
    router = {
        "online_score": method_handler,
        "clients_interests": method_handler
    }
    store = None

    def get_request_id(self, headers):
        """
        Get or create random request id
        """
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        """
        Process POST request to server
        """
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request,
                                                        "headers": self.headers},
                                                       context,
                                                       self.store)
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
