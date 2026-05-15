# FAIRlead - conceptual model extraction service

FAIRlead is a data integration framework that shall improve [FAIRness](https://www.go-fair.org/fair-principles/) of existing data sets in the energy domain.

The focus is especially on data sets that are usually not supported by enterprise data integration / enterprise application integration solutions.
This includes for example tool specific energy models, files that have been created by engineers during their daily work and some standard documents like IEC61850 and CIM.

Usually data integrations rely on specific mapping languages or scripts to extract a certain piece of information from a data source.
Since this would be unfeasible for the huge amount of custom files we want to support, another attempt is needed.
FAIRlead aims to extract the conceptual model of the included data.
In a first iteration this shall provide an ER model of a given data set.
This process can be supported by any kind of existing schema information like XML Schema files or database schemas.

With this extraction of the basic entities and relations future data integration steps are easier to express since it abstracts from the actual data serialization.

## Repository

This repository shall contain the service that is used to extract a conceptual model and provide it via a REST API or a CLI.
Moreover, a visualization via the [Graphviz software](https://graphviz.org/) shall be available.


It contains many subfolders for different Python packages.

> This list is out-of-date

- simpler-api
- simpler-cli
- simpler-core
- simpler-model
- simpler-plugin-rdf
- simpler-plugin-sql
- simpler-plugin-tabular
- simpler-plugin-xml

### Simpler API
The API folder includes the Python code to provide the functionality as a REST service.


## Usage

### Installation
At the moment, not all packages are available on PyPi, yet.
This means an installation from a clone or fork of this repo is the recommended way to install.

```shell
git clone git@github.com:Cpprentice/FAIRlead-model-extraction.git
cd FAIRlead-model-extraction
git switch develop
python -m venv .venv   # or use UV if you like
.\.venv\Scripts\activate  # on bash use source instead
pip install -e simpler-api
``` 

You will need to install the plugins for the datatypes you need. E.g.
```shell
pip install -e packages\datasource-plugin-doi
pip install -e datasource-plugin-linkml
```

Unfortunately, there are currently three evolution levels of those plugins:

- name starts with `simpler-plugin-` and location is on the top level
- name starts with `datasource-plugin-` and location is also on top level
- name starts with `datasource-plugin-` and location is in the packages subfolder

If there is sufficient free time, they will all be migrated to the third evolution.
In the meantime, you will have to check all three kinds to check for a matching plugin.

### Running the app

To start the backend server please run

```shell
python -m uvicorn simpler_api.main:app --host 0.0.0.0 --port 7373
```

The open your browser under the following URL: http://localhost:7373/frontend


### Managing available data sources

At the moment, there is no working solution yet to add new datasources from the UI.
The safest way is to manually add files to the storage path.

The default storage path is the `storage` subfolder in the top level of the repository.
If it does not exist yet, make sure to create it.

The general structure is the following:

```
storage
|
|- <data source name>
|  |
|  |- plugin.yaml
|  \- < filename >
|
\- <another data source name>
   |
   |- plugin.yaml
   \- < filename >
```

The minimal plugin.yaml for a datasource looks like the following example using the LinkML plugin:

```yaml
plugin_name: Linkml
```

Each plugin, requires their additional files to be named according to its definition.
For the LinkML plugin the content file must be called `schema` without an extension.

The available plugin names and input file names can be fetched with the `/formats` endpoint (using curl or your favorite web request tool).
A full installation might yield the following JSON overview.

> Note that the parts in square brackets indicate the type of the file and are not part of the filename

```json
[
  {
    "name": "Sqlite",
    "inputs": [
      "database[BINARY]"
    ]
  },
  {
    "name": "SQL",
    "inputs": [
      "connector[TEXT|SECURE]"
    ]
  },
  {
    "name": "JSON",
    "inputs": [
      "data[TEXT]",
      "schema[TEXT]"
    ]
  },
  {
    "name": "Tabular",
    "inputs": [
      "data_no_header[BINARY]",
      "data_header[BINARY]"
    ]
  },
  {
    "name": "Excel",
    "inputs": [
      "workbook.xlsx[BINARY]",
      "table_def.yaml[TEXT]"
    ]
  },
  {
    "name": "Parquet",
    "inputs": [
      "data[BINARY]"
    ]
  },
  {
    "name": "XML",
    "inputs": [
      "data[TEXT]",
      "xsd[TEXT]",
      "dtd[TEXT]",
      "xsd_extra[BINARY]"
    ]
  },
  {
    "name": "OWL",
    "inputs": [
      "ontology[TEXT]",
      "ontology_extension[TEXT]",
      "data[TEXT]",
      "imports[BINARY]"
    ]
  },
  {
    "name": "SPARQL",
    "inputs": [
      "connector[TEXT|SECURE]"
    ]
  },
  {
    "name": "OpenAPI",
    "inputs": [
      "spec_file[TEXT]",
      "spec_url[TEXT|SHOW_IN_JSON]"
    ]
  },
  {
    "name": "WSDL",
    "inputs": [
      "spec[BINARY]"
    ]
  },
  {
    "name": "Influx",
    "inputs": [
      "url[TEXT|SHOW_IN_JSON]",
      "user[TEXT|SECURE]",
      "password[TEXT|SECURE]",
      "token[TEXT|SECURE]"
    ]
  },
  {
    "name": "plantuml",
    "inputs": [
      "diagram[TEXT]"
    ]
  },
  {
    "name": "OpenEnergyDatabase",
    "inputs": [
      "config[TEXT|SHOW_IN_JSON]"
    ]
  },
  {
    "name": "Linkml",
    "inputs": [
      "schema[TEXT|SHOW_IN_JSON]",
      "data[TEXT]"
    ]
  },
  {
    "name": "DOI",
    "inputs": [
      "doi[TEXT|SHOW_IN_JSON]"
    ]
  }
]
```

### Quick UI overview

In the browser window, the top left navigation menu lets you chose different visualizations for the configured data sources.
There are currently five sections in this menu.

- LinkML
- LinkML Filtered
- Mappings <-- this is still WIP
- ER Diagrams
- Annotation

All but the `Mappings` section contain all your data sources as a list.
As a starting point you should usually use the `LinkML` or `LinkML Filtered` sections.
Use the filtered version if you have a large model (e.g. more than 30 classes/tables).

> In case you use the `Filtered` section, you will have to select one or more class names in the dropdown selection that appears in the title bar, before the model is being displayed.


The title bar contains more buttons to switch modes, download files or to access documentation.
There is no full documentation for that yet but it will likely be in the UI repository of FAIRlead at some point.
