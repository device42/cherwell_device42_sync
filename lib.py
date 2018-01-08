import sys
from importlib import reload

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


def get_existing_cherwell_objects(service, configuration_item, page, data):
    bus_ib_pub_ids_request_data = {
        "busObId": configuration_item,
        'includeAllFields': True,
        "pageNumber": page,
        "pageSize": 100
    }
    bus_ib_pub_ids = service.request('/api/V1/getsearchresults', 'POST', bus_ib_pub_ids_request_data)
    data += bus_ib_pub_ids["businessObjects"]
    if bus_ib_pub_ids["totalRows"] > page * 100:
        page += 1
        get_existing_cherwell_objects(service, configuration_item, page, data)

    return data


def get_existing_cherwell_objects_map(data):
    result = {}
    cnt = 0
    for item in data:
        for field in item['fields']:
            if field['name'] == 'U_device42_id':
                result[field['value']] = {
                    "busObPublicId": item["busObPublicId"],
                    "busObRecId": item["busObRecId"],
                }
                cnt += 1
    print(cnt)
    return result


def perform_butch_request(bus_object, mapping, match_map, _target, _resource, source, existing_objects_map, target_api,
                          resource_api, configuration_item):
    batch = {
        "saveRequests": [],
        "stopOnError": DEBUG
    }
    for item in source[mapping.attrib['source']]:
        batch["saveRequests"].append(
            fill_business_object(bus_object['fields'], item, configuration_item, match_map, existing_objects_map,
                                 mapping.attrib['key'], resource_api))

    response = target_api.request(_target.attrib['path'], 'POST', batch)

    if response["hasError"] and DEBUG:
        print(response['responses'][-1:][0]["errorMessage"])
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
                              resource_api, configuration_item)
    return True


def from_d42(source, mapping, _target, _resource, target_api, resource_api, configuration_item):
    fields = mapping.findall('field')
    field_names = [field.attrib['target'] for field in fields]
    match_map = {field.attrib['target']: field for field in fields}
    bus_object_config = {
        "busObId": configuration_item,
        "fieldNames": field_names
    }

    existing_objects = get_existing_cherwell_objects(target_api, configuration_item, 1, [])
    existing_objects_map = get_existing_cherwell_objects_map(existing_objects)
    bus_object = target_api.request('/api/V1/getbusinessobjecttemplate', 'POST', bus_object_config)
    success = perform_butch_request(bus_object, mapping, match_map, _target, _resource, source, existing_objects_map,
                          target_api,
                          resource_api, configuration_item)
    if success:
        print("Success")
    else:
        print("Something bad happened")


