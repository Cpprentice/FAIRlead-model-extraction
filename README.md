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


It contains many subfolders for different Python modules.

- simpler-api
- simpler-cli
- simpler-core
- simpler-model
- simpler-model-3_1
- simpler-plugin-rdf
- simpler-plugin-sql
- simpler-plugin-tabular
- simpler-plugin-xml

### Simpler API
The API folder includes the Python code to provide the functionality as a REST service.


