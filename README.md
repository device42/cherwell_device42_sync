[Device42](http://www.device42.com/) is a Continuous Discovery software for your IT Infrastructure. It helps you automatically maintain an up-to-date inventory of your physical, virtual, and cloud servers and containers, network components, software/services/applications, and their inter-relationships and inter-dependencies.


This repository contains script that helps you sync data between cherwell and Device42 back and forth.

### Download and Installation
-----------------------------
To utilize the Cherwell_device42_mapping script, Python 3.5+ is required. The following Python Packages are required as well:

* certifi==2017.11.5
* chardet==3.0.4
* idna==2.6
* requests==2.18.4
* urllib3==1.22

These can all be installed by running `pip install -r requirements.txt`.

Once installed, the script itself is run by this command: `python sync.py`.

### Configuration
-----------------------------
Prior to using the script, it must be configured to connect to your Device42 instance and your Cherwell instance. 
* Save a copy of mapping.xml.sample as mapping.xml. 
* Enter your URL, Users and Passwords in the Cherwell and Device42 sections (lines 5-11), and the Cherwell client_id as well. 
This can be obtained in Cherwell from 
cherwell service management administration -> security -> edit REST api client settings -> Client Key

Below the credential settings, you’ll see a Tasks section. 
Multiple Tasks can be setup to synchronize various CIs from Device42 to Cherwell. 
In the <api> section of each task, there will be a <resource> section that queries Device42 to obtain the desired CIs. 
Full documentation of the Device42 API and endpoints is available at https://api.device42.com. 
Individual tasks within a mapping.xml file can be enabled or disabled at will by changing the `enable="true"` to `enable="false"` in the <task> section.

Each of these CIs will be associated via the business object ID in Cherwell. 
These can be obtained in Cherwell from 
Cherwell service management administration -> blueprint -> Config - * -> edit business object -> Bus Object Properties... -> Advanced -> Business Object ID

Once the Device42 API resource and Cherwell Business Object ID are entered, the <mapping> section is where fields from Device42 (the `resource` value) can be mapped to fields in Cherwell (the `target` value). 
It is very important to adjust the list of default values in accordance between cherwell and device 42 (for example, service_level).

After configuring the fields to map as needed, the script should be ready to run. 
For debugging, there is a `DEBUG` variable in `lib.py` which can be set to `True` or `False`.
    
#### Processing Affinity Groups to Cherwell
**Requires Device42 version 15.11.07 or higher**

The configuration for synchronization Affinity Groups is a bit different and more complex since such tasks are processing several CIs simultaneously.

The <task> section has to be marked by additional attribute: `type="affinity_group"`.
Also, this section can contain an additional attribute `reset-connections="true"`. If this option is enabled, all existing connections/relationships between Services will be removed before processing new data. Set this option to `false` or remove it to sync new elements without removing old relationships.

The task has to contain at least 3 <configuration-item> tags:
1. for Service Instances (*Config-Service** CI in Cherwell; *serviceinstance* in Device42)
1. for Application Components (*Config-Application** CI in Cherwell; *appcomp* in Device42)
1. for Devices (*device* in Device42). Several <configuration-item> for devices can be present if devices are mapped to several CI's on Cherwell.

Each <configuration-item> section has to contain the following attributes:
- `d42-model`: the name of CI(model) in Device42
- `bus-ob-id`: the business object ID of CI in Cherwell
 
Each <configuration-item> section has to contain an info about relationships (<downstream-relationship> section). 
The <downstream-relationship> section represents *1 <-> Many* downstream relationship and has to contain the following attributes:
- `d42-model`: the name of CI(model) in Device42 of the 'child' in relationship
- `id`: the ID of relationship (the *CI links Downstream CIs* relationship should be used in common case). This value can be obtained in Cherwell from Cherwell service management administration -> blueprint -> Config - * -> Edit relationships... -> relationship -> Edit -> Advanced -> Relationship ID. 
For proper working, please make sure that used relationship has the reversed one (*Upstream*).

The <configuration-item> sections for Service Instances and Application Components have to contain the <mapping> section for creating new objects in Cherwell.
Mappings are not applicable for devices since they should be processed in own tasks.

See an example in the `mapping.xml.sample` file.

### Compatibility
-----------------------------
* Script runs on Linux and Windows
* Processing Affinity Groups to Cherwell requires Device42 version 16.00 or higher (not backwards compatible)

### Info
-----------------------------
* mapping.xml - file from where we get fields relations between D42 and Cherwell
* lib.py - file with integration description, we describe how fields should be migrated
* sync.py - initialization and processing file, where we prepare API calls

### Support
-----------------------------
We will support any issues you run into with the script and help answer any questions you have. Please reach out to us at support@device42.com

### Version
-----------------------------
3.1.1.201001