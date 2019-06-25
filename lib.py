import collections
import json
import sys
import urllib.parse as urllib
from importlib import reload

from doql import Doql_Util

reload(sys)

DEBUG = True


def fill_business_object(fields, data, bus_ob_id, match_map, existing_objects_map, mapping_key, source_api):
    response_object = {
        "busObId": bus_ob_id,
        "fields": []
    }
    if existing_objects_map.get(str(data[mapping_key])):
        response_object["busObRecId"] = existing_objects_map.get(str(data[mapping_key]))["busObRecId"]
    for field in fields:
        val = ''
        if match_map[field["name"]].attrib['resource']:
            if match_map[field["name"]].attrib.get("extra-api"):
                url = match_map[field["name"]].attrib.get("extra-api")
                if match_map[field["name"]].attrib.get("extra-api-additional-param"):
                    url = "{}{}".format(url, data[match_map[field["name"]].attrib.get("extra-api-additional-param")])
                response = source_api.request(url, 'GET')
                if match_map[field["name"]].attrib.get("extra-api-extra-key"):
                    response = response[match_map[field["name"]].attrib.get("extra-api-extra-key")]
                data.update(response)
            if data.get(match_map[field["name"]].attrib['resource']):
                val = data[match_map[field["name"]].attrib['resource']]
                if match_map[field["name"]].get("is-array") and val:
                    val = val[0]
                if match_map[field["name"]].get("sub-key"):
                    val = val[match_map[field["name"]].get("sub-key")]
                if field["name"] == "FriendlyName" and not val:
                    val = data["name"]
            if match_map[field["name"]].attrib.get("url"):
                val = match_map[field["name"]].attrib.get("url").format(data[match_map[field["name"]].attrib['resource']])
        if val:
            field_to_append = field.copy()
            field_to_append["dirty"] = True
            field_to_append["value"] = val
            response_object["fields"].append(field_to_append)

    return response_object


def fill_business_object_doql(fields, data, bus_ob_id, match_map, existing_objects_map, mapping_key, extend=False, primary_fk=None):
    response_object = {
        "busObId": bus_ob_id,
        "fields": []
    }
    if extend:
        if data.get(primary_fk) and existing_objects_map.get(str(data[primary_fk])):
            response_object["busObRecId"] = existing_objects_map.get(str(data[primary_fk]))["busObRecId"]
        else:
            return None
    else:
        if data.get(mapping_key) and existing_objects_map.get(str(data[mapping_key])):
            response_object["busObRecId"] = existing_objects_map.get(str(data[mapping_key]))["busObRecId"]
    for field in fields:
        val = ''
        if match_map[field["name"]].attrib['resource']:
            if data.get(match_map[field["name"]].attrib['resource']):
                val = data[match_map[field["name"]].attrib['resource']]
                if field["name"] == "FriendlyName" and not val:
                    val = data["name"]
            if match_map[field["name"]].attrib.get("url"):
                val = match_map[field["name"]].attrib.get("url").format(data[match_map[field["name"]].attrib['resource']])
        if val:
            field_to_append = field.copy()
            field_to_append["dirty"] = True
            field_to_append["value"] = val
            response_object["fields"].append(field_to_append)

    return response_object


def get_existing_cherwell_objects(service, configuration_item, page, data, fields=None):
    bus_ib_pub_ids_request_data = {
        "busObId": configuration_item,
        'includeAllFields': True,
        "pageNumber": page,
        "pageSize": 100
    }

    if isinstance(fields, collections.Iterable):
        fields = [str(field) for field in fields]
        bus_ib_pub_ids_request_data['fields'] = fields
        bus_ib_pub_ids_request_data['includeAllFields'] = False
    else:
        bus_ib_pub_ids_request_data['includeAllFields'] = True

    bus_ib_pub_ids = service.request('/api/V1/getsearchresults', 'POST', bus_ib_pub_ids_request_data)
    data += bus_ib_pub_ids["businessObjects"]
    print("Loaded {} of {} business objects".format(len(data), bus_ib_pub_ids["totalRows"]))

    if bus_ib_pub_ids["totalRows"] > page * 100:
        page += 1
        get_existing_cherwell_objects(service, configuration_item, page, data)

    return data


def get_existing_cherwell_objects_map(data, full_objects=False):
    result = {}
    cnt = 0
    for item in data:
        for field in item['fields']:
            if field['name'] == 'U_device42_id':
                cnt += 1
                if full_objects:
                    result[field['value']] = item
                    break
                else:
                    result[field['value']] = {
                        "busObPublicId": item["busObPublicId"],
                        "busObRecId": item["busObRecId"],
                    }
    print(cnt)
    return result


def get_error_msg_from_response(response):
    from functools import reduce

    try:
        errors = []
        err_objs = [response] + response.get('responses', []) + response.get('relatedBusinessObjects', [])
        for err_obj in err_objs:
            errors.append(err_obj.get('errorMessage'))
            errors += reduce(lambda ers, obj: ers + ([obj.get('error')] if obj.get('error') else []),
                             err_obj.get('fieldValidationErrors', []), [])

        errors = filter(None, errors)
        error = '; '.join(errors)

        if not error:
            error = 'Unknown error'

        return error
    except:
        return 'Unknown error'


def log_http_request(request):
    request_state = dict(
        (attr, getattr(request, attr, None))
        for attr in ['url', 'method', 'headers', 'body']
    )
    print('Request:', request_state)


def log_http_response(response):
    print('Response:', response.__getstate__())


def perform_butch_request(bus_object, mapping, match_map, _target, _resource, source, existing_objects_map, target_api,
                          resource_api, configuration_item, doql):
    batch = {
        "saveRequests": [],
        "stopOnError": DEBUG
    }

    if doql:
        for item in source[mapping.attrib['source']]:
            batch["saveRequests"].append(
                fill_business_object_doql(bus_object['fields'], item, configuration_item, match_map,
                                          existing_objects_map,
                                          mapping.attrib['key']))

            batch["saveRequests"] = list(filter(None.__ne__, batch["saveRequests"]))

        response = target_api.request(_target.attrib['path'], 'POST', batch)

        if response["hasError"] and DEBUG:
            print('error:', get_error_msg_from_response(response))
            print('path:', _target.attrib['path'])
            print('method:', 'POST')
            print('payload:', batch)
            print('response:', response)
            return False
    else:
        for item in source[mapping.attrib['source']]:
            batch["saveRequests"].append(
                fill_business_object(bus_object['fields'], item, configuration_item, match_map,
                                     existing_objects_map,
                                     mapping.attrib['key'], resource_api))

        response = target_api.request(_target.attrib['path'], 'POST', batch)

        if response["hasError"] and DEBUG:
            print('error:', get_error_msg_from_response(response))
            print('path:', _target.attrib['path'])
            print('method:', 'POST')
            print('payload:', batch)
            print('response:', response)
            return False

        offset = source.get("offset", 0)
        limit = source.get("limit", 100)
        if offset + limit < source["total_count"]:
            print("Exported {} of {} records".format(offset + limit, source["total_count"]))
            source_url = _resource.attrib['path']
            if _resource.attrib.get("extra-filter"):
                source_url += _resource.attrib.get("extra-filter") + "&amp;"
            source = resource_api.request(
                "{}offset={}".format(source_url, offset + limit),
                _resource.attrib['method'])
            perform_butch_request(bus_object, mapping, match_map, _target, _resource, source, existing_objects_map,
                                  target_api,
                                  resource_api, configuration_item, doql)
    return True


def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z


class CI:
    d42_id_field_name = 'U_device42_id'

    def __init__(self, xml_el, cherwell_api):
        self.d42_model = xml_el.attrib.get('d42-model')
        self.bus_ob_id = xml_el.attrib.get('bus-ob-id')
        self.cherwell_api = cherwell_api
        self.cherwell_items = {}

        # relationships
        relationships = {}
        for rel in xml_el.findall('downstream-relationship'):
            rel_model = rel.attrib.get('d42-model')
            rel_id = rel.attrib.get('id')

            if rel_id and rel_model:
                relationships[rel_model] = rel_id

        self.relationships = relationships

        # mappings
        fields = []
        key = None
        mapping = xml_el.find('mapping')
        if mapping:
            fields = mapping.findall('field')
            key = mapping.attrib.get('key')

        self.fields = fields
        self.field_names = [field.attrib['target'] for field in fields]
        self.match_map = {field.attrib['target']: field for field in fields}
        self.key = key

    def __str__(self):
        return 'CI(d42_model={d42_model}, bus_ob_id={bus_ob_id})'.format(
            d42_model=self.d42_model,
            bus_ob_id=self.bus_ob_id
        )

    def get_bus_obj_template(self):
        if hasattr(self, 'bus_obj_template'):
            return self.bus_obj_template
        else:
            args = {
                'busObId': self.bus_ob_id,
            }
            if self.field_names:
                args['fieldNames'] = self.field_names
            else:
                args['includeAll'] = True

            response = self.cherwell_api.request('/api/V1/getbusinessobjecttemplate', 'POST', args)

            if response.get('hasError'):
                msg = "Couldn't get business object template for model '{model}': {error}:".format(
                    model=self.d42_model,
                    error=response.get('errorMessage')
                )

                raise Exception(msg)

            else:
                self.bus_obj_template = response

            return self.bus_obj_template

    def link_child_obj(self, d42_pk, child_d42_pk, child_ci):
        relationship_id = self.relationships.get(child_ci.d42_model)
        if not relationship_id:
            raise Exception('Relationship between {parent_ci} and {child_ci} is not configured'.format(parent_ci=self, child_ci=child_ci))

        cherwell_obj = self.get_cherwell_obj(d42_pk)
        if not cherwell_obj:
            raise Exception('Cherwell object not found. CI: {ci}. D42 pk: {pk}'.format(ci=self, pk=d42_pk))

        cherwell_child = child_ci.get_cherwell_obj(child_d42_pk)
        if not cherwell_child:
            raise Exception('Cherwell object not found. CI: {ci}. D42 pk: {pk}'.format(ci=child_ci, pk=child_d42_pk))

        path = '/api/V1/linkrelatedbusinessobject/' \
               'parentbusobid/{parent_bus_ob_id}/parentbusobrecid/{parent_bus_ob_rec_id}/' \
               'relationshipid/{relationship_id}/' \
               'busobid/{bus_ob_id}/busobrecid/{bus_ob_rec_id}'.format(
            parent_bus_ob_id=self.bus_ob_id,
            parent_bus_ob_rec_id=cherwell_obj.get('busObRecId'),
            relationship_id=relationship_id,
            bus_ob_id=child_ci.bus_ob_id,
            bus_ob_rec_id=cherwell_child.get('busObRecId'),
        )

        # note: link request can return 500 if link already exists
        response = self.cherwell_api.request(path, 'GET', silent=True, return_serialized=False)

        if 400 <= response.status_code < 600:
            # error
            if response.status_code == 500 and 'DuplicateEntry' in response.text:
                # it's ok, link already exists
                return True

            if DEBUG:
                log_http_response(response)
                log_http_request(response.request)

            raise Exception("Couldn't create link between {parent_ci} and {child_ci}: {error}".format(
                parent_ci=self,
                child_ci=child_ci,
                error=response.text
            ))

        else:
            result = json.loads(response.text or '{}')
            if result.get('hasError'):
                if DEBUG:
                    log_http_response(response)
                    log_http_request(response.request)

                raise Exception("Couldn't create link between {parent_ci} and {child_ci}: {error}".format(
                    parent_ci=self,
                    child_ci=child_ci,
                    error=get_error_msg_from_response(result)
                ))

    def unlink_related_objects(self, child_ci):
        relationship_id = self.relationships.get(child_ci.d42_model)
        if not relationship_id:
            raise Exception('Relationship between {parent_ci} and {child_ci} is not configured'.format(parent_ci=self,
                                                                                                       child_ci=child_ci))

        for pk, cherwell_obj in self.cherwell_items.items():
            related_objects = self.get_related_cherwell_objects(pk, relationship_id)
            for cherwell_child in related_objects:
                path = '/api/V1/unlinkrelatedbusinessobject/' \
                       'parentbusobid/{parent_bus_ob_id}/parentbusobrecid/{parent_bus_ob_rec_id}/' \
                       'relationshipid/{relationship_id}/' \
                       'busobid/{bus_ob_id}/busobrecid/{bus_ob_rec_id}'.format(
                    parent_bus_ob_id=self.bus_ob_id,
                    parent_bus_ob_rec_id=cherwell_obj.get('busObRecId'),
                    relationship_id=relationship_id,
                    bus_ob_id=child_ci.bus_ob_id,
                    bus_ob_rec_id=cherwell_child.get('busObRecId'),
                )

                response = self.cherwell_api.request(path, 'DELETE', )
                if response.get('hasError'):
                    raise Exception("Couldn't delete link between {parent_ci} and {child_ci}: {error}".format(
                        parent_ci=self,
                        child_ci=child_ci,
                        error=get_error_msg_from_response(response)
                    ))

    def refresh_existing_cherwell_objects(self, fields=()):
        field_ids = []

        for f in fields:
            field_id = next(
                (field.get('fieldId') for field in self.get_bus_obj_template().get('fields', []) if field.get('name') == f),
                None
            )
            if field_id:
                field_ids.append(field_id)

        items = get_existing_cherwell_objects(self.cherwell_api, self.bus_ob_id, 1, [], field_ids)
        self.cherwell_items = get_existing_cherwell_objects_map(items, full_objects=True)

    def get_related_cherwell_objects(self, d42_pk, relationship_id, params=None):
        cherwell_obj = self.get_cherwell_obj(d42_pk)
        if not cherwell_obj:
            raise Exception('Cherwell object not found')

        def_params = {
            'pageNumber': 1,
            'pageSize': 200,
            'allfields': False,
        }

        if not params:
            params = def_params
        else:
            params = merge_two_dicts(def_params, params)

        res = []
        path = '/api/V1/getrelatedbusinessobject/' \
               'parentbusobid/{parent_bus_ob_id}/parentbusobrecid/{parent_bus_ob_rec_id}/' \
               'relationshipid/{relationship_id}/?'.format(
            parent_bus_ob_id=self.bus_ob_id,
            parent_bus_ob_rec_id=cherwell_obj.get('busObRecId'),
            relationship_id=relationship_id
        )

        while True:
            response = self.cherwell_api.request(path + urllib.urlencode(params), 'GET')

            if response.get("hasError"):
                msg = "Couldn't get related objects for {parent_ci} by relationship_id {relationship_id}: {error}".format(
                    parent_ci=self,
                    relationship_id=relationship_id,
                    error=get_error_msg_from_response(response)
                )
                raise Exception(msg)

            res += response.get('relatedBusinessObjects', [])
            if response.get('totalRecords', 0) > response.get('pageNumber') * params.get('pageSize'):
                params['pageNumber'] = response.get('pageNumber') + 1
            else:
                break

        return res

    def cherwell_obj_exists(self, d42_pk):
        return d42_pk in self.cherwell_items

    def get_cherwell_obj(self, d42_pk):
        return self.cherwell_items.get(str(d42_pk))

    def fill_cherwell_obj_doql(self, d42_obj):
        return fill_business_object_doql(
            self.get_bus_obj_template().get('fields', []),
            d42_obj,
            self.bus_ob_id,
            self.match_map,
            self.cherwell_items,
            self.key
        )

    def batch_save_cherwell_objects(self, path, d42_models_list):
        if not d42_models_list:
            return True

        batch = {
            "saveRequests": [self.fill_cherwell_obj_doql(item) for item in d42_models_list],
            "stopOnError": DEBUG
        }
        response = self.cherwell_api.request(path, 'POST', batch)

        if response["hasError"] and DEBUG:
            msg = "Couldn't save Cherwell objects: {error}".format(error=get_error_msg_from_response(response))
            raise Exception(msg)


def affinity_group_from_d42(source, _target, _resource, target_api, resource_api, src_configuration_items, reset_connections):
    from datetime import datetime

    def find_ci(d42_pk, d42_model, configuration_items):
        return next(
            (ci for ci in configuration_items.values() if
             ci.d42_model == d42_model and ci.cherwell_obj_exists(str(d42_pk))),
            None
        )

    print('Started at %s' % datetime.now())

    doql_util = Doql_Util()
    source = doql_util.csv_to_json(source)

    configuration_items = {}
    service_ci = None
    appcomp_ci = None
    for xml_ci in src_configuration_items:
        ci = CI(xml_ci, target_api)
        configuration_items[ci.bus_ob_id] = ci

        if ci.d42_model == 'serviceinstance':
            service_ci = ci
        elif ci.d42_model == 'appcomp':
            appcomp_ci = ci

    if not service_ci:
        print('Configuration item for service instances is not provided')
        exit(1)

    if not appcomp_ci:
        print('Configuration item for appcomps is not provided')
        exit(1)

    # 1 get existing items
    print('Retrieving existing business objects')
    for ci in configuration_items.values():
        ci.refresh_existing_cherwell_objects(['U_device42_id'])

    # 1.1 clear relationships
    if reset_connections:
        print('Removing old connections')
        service_ci.unlink_related_objects(service_ci)

    # 2 process items
    services_to_create = {}
    appcomps_to_create = {}
    device_to_service = {}
    device_to_appcomp = {}
    appcomp_to_service = {}
    service_to_service = {}

    for row in source:
        req_props = ['dependency_device_fk', 'dependency_serviceinstance_fk', 'dependent_device_fk', 'dependent_serviceinstance_fk']
        if not all(map(lambda key: row.get(key), req_props)):
            continue

        # process nodes
        for pref in ('dependency_', 'dependent_'):
            service_pk = row.get(pref + service_ci.key)
            device_pk = row.get(pref + 'device_fk')
            appcomp_pk = row.get(pref + appcomp_ci.key)
            service = None
            if not service_ci.cherwell_obj_exists(service_pk) and service_pk and service_pk not in services_to_create:
                service = {field.attrib['resource']: row.get(pref + field.attrib['resource']) for field in service_ci.match_map.values()}
                services_to_create[service_pk] = service

                # only for new services
                if device_pk:
                    conn_key = '%s:%s' % (device_pk, service_pk)
                    if conn_key not in device_to_service:
                        device_to_service[conn_key] = {
                            'device': device_pk,
                            'service': service_pk,
                        }

            if not service and service_pk:
                service = services_to_create.get(service_pk)

            if appcomp_pk and not appcomp_ci.cherwell_obj_exists(appcomp_pk) and appcomp_pk not in appcomps_to_create:
                appcomp = {field.attrib['resource']: row.get(pref + field.attrib['resource']) for field in appcomp_ci.match_map.values()}
                appcomps_to_create[appcomp_pk] = appcomp

                # only for new appcomps
                appcomp_device_pk = row.get(pref + 'appcomp_device_fk')
                if appcomp_device_pk:
                    conn_key = '%s:%s' % (appcomp_device_pk, appcomp_pk)
                    if conn_key not in device_to_appcomp:
                        device_to_appcomp[conn_key] = {
                            'device': appcomp_device_pk,
                            'appcomp': appcomp_pk,
                        }

            # only for new services
            if service and appcomp_pk:
                conn_key = '%s:%s' % (appcomp_pk, service_pk)
                if conn_key not in appcomp_to_service:
                    appcomp_to_service[conn_key] = {
                        'service': service_pk,
                        'appcomp': appcomp_pk,
                    }

        dependency_service_pk = row.get('dependency_' + service_ci.key)
        dependent_service_pk = row.get('dependent_' + service_ci.key)
        if dependency_service_pk and dependent_service_pk:
            conn_key = '%s:%s' % (dependency_service_pk, dependent_service_pk)
            if conn_key not in service_to_service:
                service_to_service[conn_key] = {
                    'from': dependency_service_pk,
                    'to': dependent_service_pk,
                }

    # perform batch requests for creating services and appcomps
    if len(appcomps_to_create) or len(services_to_create):
        print('Creating new business objects')
        if len(appcomps_to_create):
            appcomp_ci.batch_save_cherwell_objects(_target.attrib['path'], appcomps_to_create.values())
            print('Created %s Applications' % len(appcomps_to_create))

        if len(services_to_create):
            service_ci.batch_save_cherwell_objects(_target.attrib['path'], services_to_create.values())
            print('Created %s Services' % len(services_to_create))

    # refresh existing items
    if len(appcomps_to_create) or len(services_to_create):
        print('Refreshing existing business objects')

    if len(appcomps_to_create):
        appcomp_ci.refresh_existing_cherwell_objects([CI.d42_id_field_name])

    if len(services_to_create):
        service_ci.refresh_existing_cherwell_objects([CI.d42_id_field_name])

    # create links Device->Appcomp for new appcomps
    if len(device_to_appcomp):
        print('Creating links between new Applications and Devices')

    for link in device_to_appcomp.values():
        d42_device_pk = link.get('device')
        d42_appcomp_pk = link.get('appcomp')

        appcomp = appcomp_ci.get_cherwell_obj(d42_appcomp_pk)
        device_ci = find_ci(d42_device_pk, 'device', configuration_items) if appcomp else None

        if device_ci and appcomp:
            device_ci.link_child_obj(
                d42_pk=d42_device_pk,
                child_d42_pk=d42_appcomp_pk,
                child_ci=appcomp_ci
            )

    if len(device_to_service):
        print('Creating links between new Services and Devices')

    for link in device_to_service.values():
        d42_device_pk = link.get('device')
        d42_service_pk = link.get('service')

        service = service_ci.get_cherwell_obj(d42_service_pk)
        device_ci = find_ci(d42_device_pk, 'device', configuration_items) if service else None

        if device_ci and service:
            device_ci.link_child_obj(
                d42_pk=d42_device_pk,
                child_d42_pk=d42_service_pk,
                child_ci=service_ci
            )

    if len(appcomp_to_service):
        print('Creating links between new Services and Application Components')

    for link in appcomp_to_service.values():
        d42_appcomp_pk = link.get('appcomp')
        d42_service_pk = link.get('service')

        service = service_ci.get_cherwell_obj(d42_service_pk)
        appcomp = appcomp_ci.get_cherwell_obj(d42_appcomp_pk)

        if appcomp and service:
            appcomp_ci.link_child_obj(
                d42_pk=d42_appcomp_pk,
                child_d42_pk=d42_service_pk,
                child_ci=service_ci
            )

    # 3 create links services -> services (process connections)
    links_num = 0
    if len(service_to_service):
        print('Creating links between Services')

        s_to_s_relationship_id = service_ci.relationships.get(service_ci.d42_model)
        if not s_to_s_relationship_id:
            raise Exception(
                'Relationship between {parent_ci} and {child_ci} is not configured'.format(parent_ci=service_ci,
                                                                                           child_ci=service_ci)
            )

        link_tmpl = '{parent_pk}:{child_pk}'
        links_cache = []
        processed_parent_services_pk = []
        d42_id_field_name = CI.d42_id_field_name.lower()

        for link in service_to_service.values():
            parent_pk = link.get('from')
            parent = service_ci.get_cherwell_obj(parent_pk)
            if not parent:
                continue

            child_pk = link.get('to')
            child = service_ci.get_cherwell_obj(child_pk)
            if not child:
                continue

            # check existing parent connections
            if not reset_connections and \
                    parent_pk not in processed_parent_services_pk and \
                    parent_pk not in services_to_create:
                processed_parent_services_pk.append(parent_pk)
                related_objects = service_ci.get_related_cherwell_objects(parent_pk, s_to_s_relationship_id,
                                                                          {'allfields': True})
                for related in related_objects:
                    for field in related.get('fields', []):
                        if field.get('name').lower() == d42_id_field_name:
                            link_key = link_tmpl.format(parent_pk=parent_pk, child_pk=field.get('value'))
                            links_cache.append(link_key)
                            break

            link_key = link_tmpl.format(parent_pk=parent_pk, child_pk=child_pk)

            if link_key not in links_cache:
                service_ci.link_child_obj(
                    d42_pk=parent_pk,
                    child_d42_pk=child_pk,
                    child_ci=service_ci
                )
                links_cache.append(link_key)
                links_num += 1

                if links_num % 100 == 0:
                    print("Added %s 'Service(Client) to Service(Listener)' links" % links_num)

    print("Added %s 'Service(Client) to Service(Listener)' links" % links_num)
    print('Finished at %s' % datetime.now())

    return True


def from_d42(source, mapping, _target, _resource, target_api, resource_api, configuration_item, doql=False):
    fields = mapping.findall('field')
    field_names = [field.attrib['target'] for field in fields]
    match_map = {field.attrib['target']: field for field in fields}
    bus_object_config = {
        "busObId": configuration_item,
        "fieldNames": field_names
    }

    if doql is True:
        doql_util = Doql_Util()

        source = doql_util.csv_to_json(
            source,
            mapping_source=mapping.attrib['source']
        )


    existing_objects = get_existing_cherwell_objects(target_api, configuration_item, 1, [])
    existing_objects_map = get_existing_cherwell_objects_map(existing_objects)
    bus_object = target_api.request('/api/V1/getbusinessobjecttemplate', 'POST', bus_object_config)
    success = perform_butch_request(bus_object, mapping, match_map, _target, _resource, source, existing_objects_map,
                          target_api,
                          resource_api, configuration_item, doql)
    if success:
        print("Success")
    else:
        print("Something bad happened")


def perform_delete_butch_request(_target, target_api, items_to_delete, bus_object_id):
    batch = {
        'deleteRequests': [],
        'stopOnError': DEBUG
    }

    for item in items_to_delete:
        batch['deleteRequests'].append({
            'busObId': bus_object_id,
            'busObPublicId': item['busObPublicId'],
            'busObRecId': item['busObRecId'],
        })

    response = target_api.request(_target.attrib['path'], 'POST', batch)

    if response['hasError'] and DEBUG:
        print('error:', get_error_msg_from_response(response))
        print('path:', _target.attrib['path'])
        print('method:', 'POST')
        print('payload:', batch)
        print('response:', response)
        return False

    return True


def delete_objects_from_server(_target, target_api, configuration_item):
    existing_objects = get_existing_cherwell_objects(target_api, configuration_item, 1, [])
    success = perform_delete_butch_request(_target, target_api, existing_objects, configuration_item)

    if success:
        print('Success')
    else:
        print('Something bad happened')
