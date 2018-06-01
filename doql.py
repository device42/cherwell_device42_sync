import base64
import csv
import json
import sys

import requests


class Doql_Util():

    def csv_to_json(self, doql_csv, mapping_source=None):
        listrows = doql_csv.split('\n')
        fields = listrows[0].split(',')
        rows = csv.reader(listrows[1:-1])
        out = []
        for row in rows:
            items = zip(fields, row)
            item = {}
            for (name, value) in items:
                item[name] = value.strip()
            # dont add empty objects
            
            out.append(item)

        # if mapping_source, store all items under mapping_source
        # to conform to shape of API results
        if mapping_source is not None: 
            out = {mapping_source: out}
            return out
        return out


'''
POST https://10.42.2.241/services/data/v1.0/query/
query:SELECT * FROM view_assetaction_v1
header:yes

payload = {
    "query": "SELECT * FROM view_ipaddress_v1",
    "header": "yes"
}

header = {
    'Authorization': 'Basic ' + base64.b64encode(
        ('xxxx' + ':' + 'xxxxx').encode()
    ).decode(),
    'Content-Type': 'application/x-www-form-urlencoded'
}

url = "https://10.42.2.241/services/data/v1.0/query/?quote=\""
resp = requests.post(url, data=payload, headers=header, verify=False)

doql_util = Doql_Util()
jsonified = doql_util.csv_to_json(resp.text)
print(json.dumps(jsonified, indent=2))
'''
