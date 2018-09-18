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


class Cherwell(Service):
    def __init__(self, settings):
        super().__init__(settings)
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

    def request(self, path, method, data=()):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(self.access_token)
        }
        result = {}
        if method == 'GET':
            response = requests.get(self.url + path, headers=headers, verify=False)
        elif method == 'POST':
            response = requests.post(self.url + path, json.dumps(data), headers=headers, verify=False)
        else:
            return result

        validate_response(response)
        result = deserialize_json(response.content.decode())

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
    configuration_item = task.find('configuration-item').attrib['bus-ob-id']

    if _resource.attrib['target'] == 'cherwell':
        resource_api = services['cherwell']
        target_api = services['device42']
    else:
        resource_api = services['device42']
        target_api = services['cherwell']

    mapping = task.find('mapping')
    source_url = _resource.attrib['path']

    method = _resource.attrib['method']
    doql = None

    if _target.attrib.get('delete'):
        lib.delete_objects_from_server(_target, target_api, configuration_item)
        return

    if _resource.attrib.get("extra-filter"):
        source_url += _resource.attrib.get("extra-filter") + "&amp;"
        # source will contain the objects from the _resource endpoint

    if _resource.attrib.get('doql'):
        doql = _resource.attrib['doql']

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

    # source = resource_api.request(source_url, _resource.attrib['method'])
    # lib.from_d42(source, mapping, _target, _resource, target_api, resource_api, configuration_item)


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
