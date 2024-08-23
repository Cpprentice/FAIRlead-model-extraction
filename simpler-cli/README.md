# Simple ER CLI

This is the CLI for the Simple ER Extraction [Framework](https://github.com/Cpprentice/FAIRlead-model-extraction).

## Usage

The CLI provides several commands.
You can get the help for each command by using the following:

```bash
python -m simpler_cli <command> --help
```

And replacing the command placeholder with the respective command of interest.

### extract

This command extracts an entity-relationship model from the specified data set.
It supports various output formats.
The most common ones are the Graphviz DOT format and YAML to represent the frameworks own ER model serialization.

### schema

This command takes a full YAML ER model specification and an extension file as input.
It prints the combined model to stdout.

### dot

This command converts from YAML serialization to a graphviz Dot format.
