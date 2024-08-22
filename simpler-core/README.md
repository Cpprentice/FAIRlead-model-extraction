# Simpler Core
This package contains some core functionalities used within the simple ER schema extraction [project](https://github.com/Cpprentice/FAIRlead-model-extraction).

## Plugin system

To handle different types of data sources - there is a plugin system that allows to simply add new python modules with a given name pattern of `simpler_plugin_*` that will automatically be imported and made available in the API or CLI.
The base classes for each plugin are included in this package.


## ER model schema loading and merging

An ER model needs to be loadable from YAML and also user customizations need to be loadable from partial files to form the ER model that is used for any following extraction process.

## Graphviz diagram creation

This package includes the basic functionality to create dot files or svg files if graphviz can be found in the path.

## Owlready2 utils

Some utilities to extract ER concepts from OWL data.

## Storage system

To run the API it is important to provide some means of data storage. Both a base class and multiple implementations
for storage systems exist.

## Cardinality utils

Some utility functions that can be reused by plugins to handle cardinalities properly.

