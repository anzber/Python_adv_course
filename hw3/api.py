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

from scoring import get_score, get_interests
from store import TarantoolStore

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
GENDER_LIST = [UNKNOWN, MALE, FEMALE]

def add_years(dt, years):
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        if (dt.month == 2) and (dt.day == 29):
            return dt.replace(year=dt.year + years, day=28)

class ValidationError(Exception):
    """
    Error for check validation fails
    """
    pass

class BaseField(metaclass=ABCMeta):
    """
    Base half-abstract class for fields.
    Child classes should implement check_validity
    """
    def __init__(self, required, nullable=False):
        self.required = required
        self.nullable = nullable

    @abstractmethod
    def check_validity(self, field_name, value):
        """
        Abstract method for check if field is valid
        """

class CharField(BaseField):
    """
    Char field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - value is string
        """
        if not isinstance(value, str):
            raise ValidationError(f'{field_name}: value must be string')


class ArgumentsField(BaseField):
    """
    Arguments Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - value is dict
        """
        if not isinstance(value, dict):
            raise ValidationError(f'{field_name}: value must be dict')


class EmailField(CharField):
    """
    Email Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - value is string and has @
        """
        super(EmailField, self).check_validity(field_name, value)
        if ('@' not in value):
            raise ValidationError(f'{field_name}: value must contain @')


class PhoneField(BaseField):
    """
    Phone Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - starts with 7, has 11 symbols
        Can be empty
        """
        if not value:
            return
        if not isinstance(value, (int, str)):
            raise ValidationError(f'{field_name}: value must be str or int')
        if len(str(value)) != 11:
            raise ValidationError(f'{field_name}: the length of value should be equal to 11')
        if str(value)[0] != '7':
            raise ValidationError(f'{field_name}: first digit should be  7')


class DateField(BaseField):
    """
    Date Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - any valid date with format dd.mm.yyyy
        """
        if not isinstance(value, str):
            raise ValidationError(f'{field_name}: value must be str')
        try:
            if value:
                datetime.datetime.strptime(value, "%d.%m.%Y")
        except:
            raise ValidationError(f'{field_name}: wrong date format, expected format is DD.MM.YYYY')


class BirthDayField(DateField):
    """
    Birthday Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - any valid date with format dd.mm.yyyy
        No more than 70 years ago
        """
        super().check_validity(field_name, value)
        if not value:
            return
        date_birthday = datetime.datetime.strptime(value, "%d.%m.%Y")
        date_70years_before = add_years(datetime.datetime.now(), -70)
        if date_birthday < date_70years_before:
            raise ValidationError(f"{field_name}: can't be earlier than 70 years ago")
        if datetime.datetime.now() < date_birthday:
            raise ValidationError(f"{field_name}: can't be in the future")

class GenderField(BaseField):
    """
    Gender Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - one of fixed set
        """
        if value not in GENDER_LIST:
            genders_str = ','.join([str(g) for g in GENDER_LIST])
            raise ValidationError(f"{field_name}: Value is out of correct set ({genders_str})")


class ClientIDsField(BaseField):
    """
    Client IDs Field
    """
    def check_validity(self, field_name, value):
        """
        Check validity condition - list of integers
        """
        if not isinstance(value, list):
            raise ValidationError(f'{field_name}: value must be a list')
        if not value:
            raise ValidationError(f'{field_name}: list can not be empty')
        for client_id in value:
            if not isinstance(client_id, int):
                raise ValidationError(f'{field_name}: ID must be int')


class BaseMethod():
    """
    Parent class for parsing and validating json requests
    """
    def __init__(self, request):
        """
        During init request fields shoulf are parsed and as a result we get an object
        with fields initialized by request field values
        :param request: dict Dictionary containing request fields
        """
        self.missed_required = []
        self.parameters = {}
        self.wrong_fields = []

        for field, value in request.items():
            if field not in self.__class__.__dict__:
                continue
            setattr(self, field, value) # Seting field value to object instance
            self.parameters[field] = value


    def check_request_validity(self):
        # iterate over class fields (instance of BaseField)
        for field_name, field in self.__class__.__dict__.items():
            if not isinstance(field, BaseField):
                continue
            # check if param in request
            # get field of object (which has the same name as class field)
            field_value = getattr(self, field_name)
            if isinstance(field_value, BaseField):
                #if field of object is instance of BaseField then object field doesn't exist
                if field.required:
                    self.missed_required.append(field_name)
            else:
                try:
                    field.check_validity(field_name, field_value)
                except ValidationError as e:
                    self.wrong_fields.append(str(e))
        return not (self.wrong_fields or self.missed_required)

    def get_request_errors(self):
        """
        Common validity checking
        """
        if self.missed_required:
            return "Missed required arguments: " + ", ".join(self.missed_required)
        if self.wrong_fields:
            return "Wrong field values: " + ", ".join(self.wrong_fields)
        return ''

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

        if not super().check_request_validity():
            return False
        valid_pairs = [('phone', 'email'), ('first_name', 'last_name'), ('gender', 'birthday')]
        self.has_valid_pair = False
        for field1, field2 in valid_pairs:
            if check_valid_pair(getattr(self, field1), getattr(self, field2)):
                self.has_valid_pair = True
                break
        return self.has_valid_pair

    def get_request_errors(self):
        errors = super().get_request_errors()
        if errors:
            return errors
        if not self.has_valid_pair:
            return 'No valid field pair presented'
        return ''


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
    if not online_score_request.check_request_validity():
        error_message = online_score_request.get_request_errors()
        return error_message, INVALID_REQUEST
    ctx['has'] = [key for key in online_score_request.parameters]
    if method_request.is_admin:
        return {'score': 42}, OK
    return {'score': get_score(store, **online_score_request.parameters)}, OK


def clients_interests_handler(method_request, ctx, store):
    """
    Process clientsinterests request and return response
    """
    clients_interests_request = ClientsInterestsRequest(method_request.arguments)
    if not clients_interests_request.check_request_validity():
        error_message = clients_interests_request.get_request_errors()
        return error_message, INVALID_REQUEST
    ctx['nclients'] = len(clients_interests_request.client_ids)
    response = {}
    for id in clients_interests_request.client_ids:
        interests = get_interests(store, id)
        if interests:
            response[str(id)] = interests
    if response:
        return response, OK
    else:
        return 'Not Found any of client ids', NOT_FOUND


def method_handler(request, ctx, store):
    """
    Common request processing and routing to specific handler
    """
    method_request = MethodRequest(request['body'])
    if not method_request.check_request_validity():
        error_message = method_request.get_request_errors()
        return error_message, INVALID_REQUEST

    if not check_auth(method_request):
        return '', FORBIDDEN

    method_router = {
        "online_score": online_score_handler,
        "clients_interests": clients_interests_handler
    }
    if method_request.method in method_router:
        return method_router[method_request.method](method_request, ctx, store)
    return '', NOT_FOUND


class MainHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler
    """
    router = {
        "online_score": method_handler,
        "clients_interests": method_handler
    }
    store = TarantoolStore()

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
            request = json.loads(data_string.decode('utf-8'))
        except Exception as e:
            logging.exception("Bad request error: %s" % e)
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
        self.wfile.write(json.dumps(r).encode('utf-8'))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.NOTSET,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
