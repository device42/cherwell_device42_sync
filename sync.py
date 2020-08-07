import json
import base64
import requests
import urllib.parse as urllib
import xml.etree.ElementTree as eTree
import traceback
import lib
from lib import DEBUG
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from sys import exit


class Service:
    def __init__(self, settings):
        self.user = settings.attrib["user"]
        self.password = settings.attrib["password"]
        self.url = settings.attrib["url"]
        self.settings = settings


class Cherwell(Service):
    def __init__(self, settings):
        super(Cherwell).__init__(settings)
        headers = {
            'accept': "application/json",
            'content-type': "application/x-www-form-urlencoded",
        }
        data = (
            ('password', bytes(self.password, 'utf-8')),
            ('username', self.user),
            ('client_id', settings.attrib["client_id"]),
            ('grant_type', 'password'),
        )
        payload = urllib.urlencode(data, encoding='latin')
        url = "%s/token" % (self.url,)

        response = requests.request("POST", url, data=payload, headers=headers)
        validate_response(response)
        response_data = deserialize_json(response.content.decode('utf-8'))
        self.access_token = response_data['access_token']
        self.refresh_token = response_data['refresh_token']

    def refresh_access_token(self):
        headers = {
            'accept': "application/json",
            'content-type': "application/x-www-form-urlencoded",
        }
        data = (
            ('client_id', self.settings.attrib['client_id']),
            ('grant_type', 'refresh_token'),
            ('refresh_token', self.refresh_token),
        )
        payload = urllib.urlencode(data, encoding='latin')
        url = "%s/token" % (self.url,)

        response = requests.request("POST", url, data=payload, headers=headers)
        validate_response(response)
        response_data = deserialize_json(response.content.decode('utf-8'))
        self.access_token = response_data['access_token']
        self.refresh_token = response_data['refresh_token']

    def request(self, path, method, data=(), silent=False, return_serialized=True):

        def perform_request(path, method, data=()):
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer {}".format(self.access_token)
            }

            response = None
            if method == 'GET':
                response = requests.get(self.url + path, headers=headers, verify=False)
            elif method == 'POST':
                response = requests.post(self.url + path, json.dumps(data), headers=headers, verify=False)
            elif method == 'DELETE':
                response = requests.delete(self.url + path, headers=headers, verify=False)

            return response

        result = {}

        if method not in ('GET', 'POST', 'DELETE'):
            return result

        response = perform_request(path, method, data)

        if response.status_code == 401 and self.refresh_token:
            # reauthorize
            self.refresh_access_token()
            # run request again
            response = perform_request(path, method, data)

        if not silent:
            validate_response(response)

        if return_serialized:
            if len(response.content):
                result = deserialize_json(response.content.decode())
        else:
            result = response

        return result


class Device42(Service):
    def request(self, path, method, data=(), doql=None):
        headers = {
            'Authorization': 'Basic ' + base64.b64encode((self.user + ':' + self.password).encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        result = None

        if method == 'GET':
            response = requests.get(self.url + path, headers=headers, verify=False)
            validate_response(response)
            result = deserialize_json(response.content.decode())
        if method == 'POST' and doql is not None:
            payload = {
                "query": doql,
                "header": "yes"
            }
            response = requests.post(
                self.url + path,
                headers=headers,
                verify=False,
                data=payload
            )
            validate_response(response)
            result = response.text

            # validate DOQL response
            headers = result.split('\n')[0]
            if 'error:' in headers.lower():
                print('Error in DOQL query:', headers)
                exit(1)

        return result


def deserialize_json(s):
    try:
        return json.loads(s)
    except Exception as err:
        if DEBUG:
            print('Error upon deserialization JSON:', str(err))
            print('Source:', str(s))
            traceback.print_stack()
        else:
            print('Error upon deserialization JSON')
        raise err


def validate_response(response):
    try:
        response.raise_for_status()
    except Exception as err:
        print(err)
        if DEBUG:
            # show states of request and response
            request_state = dict(
                (attr, getattr(response.request, attr, None))
                for attr in ['url', 'method', 'headers', 'body']
            )
            print('Request:', request_state)
            print('Response:', response.__getstate__())
            traceback.print_stack()
        else:
            print(response.text)
        exit(1)


def init_services(settings):
    return {
        'cherwell': Cherwell(settings.find('cherwell')),
        'device42': Device42(settings.find('device42'))
    }


def task_execute(task, services):
    print('Execute task:', task.attrib['description'])

    _resource = task.find('api/resource')
    _target = task.find('api/target')

    if _resource.attrib['target'] == 'cherwell':
        resource_api = services['cherwell']
        target_api = services['device42']
    else:
        resource_api = services['device42']
        target_api = services['cherwell']

    method = _resource.attrib['method']
    doql = _resource.attrib.get('doql')

    source_url = _resource.attrib['path']
    if _resource.attrib.get("extra-filter"):
        source_url += _resource.attrib.get("extra-filter") + "&amp;"
        # source will contain the objects from the _resource endpoint

    if task.attrib.get('type') == 'affinity_group':
        configuration_items = task.findall('configuration-item')

        if doql:
            reset_connections = task.attrib.get('reset-connections') == 'true'
            source = resource_api.request(source_url, method, doql=doql)
            lib.affinity_group_from_d42(
                source,
                _target,
                _resource,
                target_api,
                resource_api,
                configuration_items,
                reset_connections
            )
            return True
        else:
            print("The 'doql' attribute in <resource> is required for this task")
            exit(1)

    mapping = task.find('mapping')
    configuration_item = task.find('configuration-item').attrib['bus-ob-id']

    if _target.attrib.get('delete'):
        lib.delete_objects_from_server(_target, target_api, configuration_item)
        return

    if doql is not None:
        source = resource_api.request(source_url, method, doql=doql)
        lib.from_d42(
            source, mapping,
            _target, _resource,
            target_api, resource_api,
            configuration_item,
            doql=True
        )

    else:
        source = resource_api.request(source_url, method)
        lib.from_d42(
            source, mapping,
            _target, _resource,
            target_api, resource_api,
            configuration_item,
            doql=False
        )


print('Running...')

# Load mapping
config = eTree.parse('mapping.xml')
meta = config.getroot()

# Init transports services
services = init_services(meta.find('settings'))

# Parse tasks
tasks = meta.find('tasks')
for task in tasks:
    if task.attrib['enable'] == 'true':
        task_execute(task, services)
