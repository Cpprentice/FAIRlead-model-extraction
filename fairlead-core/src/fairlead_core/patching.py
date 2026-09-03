import abc
import collections
import re
from dataclasses import asdict
from enum import Enum
from typing import ClassVar, Any

import Levenshtein
import rdflib
import rdflib.plugins.sparql
import rdflib.plugins.stores.sparqlstore
from jsonasobj2 import as_json, as_dict
from jsonpatch_trigger.common import serialize_jsonpath, convert_pointer_to_path, escape_json_pointer_part
from jsonpatch_trigger.compat import PydanticJSONPath
from jsonpatch_trigger.parents import make_parent_key_pairs
from jsonpatch_trigger.preconditions import Precondition, DoesNotExistPreconditionFunction
from jsonpatch_trigger.tracking import TrackingJSONPatch, AddRegistrationMixin
from linkml_runtime.linkml_model import SchemaDefinition, SlotDefinition
from linkml_runtime.linkml_model.units import UnitOfMeasure
from pydantic import BaseModel, Field
from jsonpatch_trigger import (CompoundOperation, make_jsonpath, CopyOperation, RemoveOperation,
                            AddOperation, MoveOperation, AutomatedOperationProducer, Operation,
                            OperationExecutionContext)
from jsonpatch_trigger.operations import PairwisePointerPairConstraintResolver
from jsonpath import JSONPath, JSONPointer
import jsonpath

from fairlead_core.settings import OptimizationSettings
from fairlead_core.units import search_unit_iri_by_symbol, fetch_unit_object_from_qudt_unit_iri, \
    find_best_matching_unit_for_text
from fairlead_core.performance import profile
from simpler_model import SchemaEnhancement, GenericEnhancementOperation, GenericEnhancementHandler, \
    OntologicalAnnotation, Unit


def convert_generic_operation_to_dict(generic: GenericEnhancementOperation) -> dict:
    data = generic.model_dump()
    attributes = data.pop('attributes')
    if attributes is None:
        attributes = {}
    data.update(attributes)
    return data


def convert_generic_handler_to_dict(generic: GenericEnhancementHandler) -> dict:
    data = generic.model_dump()
    attributes = data.pop('attributes')
    if attributes is None:
        attributes = {}
    data.update(attributes)
    return data

def convert_generic_operation_to_actual_operation(generic: GenericEnhancementOperation) -> Operation:
    return Operation.model_validate(convert_generic_operation_to_dict(generic))


def convert_generic_handler_to_actual_producer(generic: GenericEnhancementHandler) -> AutomatedOperationProducer:
    return AutomatedOperationProducer.model_validate(convert_generic_handler_to_dict(generic))


def convert_execution_context_to_frontend_version(ctx: OperationExecutionContext):
    data = ctx.serialize()
    return SchemaEnhancement.from_dict(dict(operations=data['operations'], producers=data['producers']))


def convert_schema_enhancement_to_execution_context(schema_enhancement: SchemaEnhancement) -> OperationExecutionContext:
    operations = [
        convert_generic_operation_to_dict(generic)
        for generic in schema_enhancement.operations
    ]
    producers = [
        convert_generic_handler_to_dict(generic)
        for generic in schema_enhancement.producers
    ]
    return OperationExecutionContext.deserialize(dict(operations=operations, producers=producers))


class MoveAttributeToRelationOperation(CompoundOperation):

    new_range: str

    def __init__(self, **data: Any):
        locator: JSONPath = data['locator']
        attribute_name = locator.segments[-1].selectors[0].name
        target_locator = make_jsonpath(f'$.slots.{attribute_name}')
        class_name = locator.segments[1].selectors[0].name
        class_slots_locator =  make_jsonpath(f'$.classes.{class_name}.slots[-1]')
        data['inner_operations'] = [
            CopyOperation(
                locator=locator,
                target_locator=target_locator,
                # target_key=locator.segments[-1].name
            ),
            RemoveOperation(
                locator=locator,
                # key=locator.segments[-1].name
            ),
            AddOperation(
                locator=make_jsonpath(f'{target_locator}.range'),
                value=data['new_range']
            ),
            AddOperation(
                locator=class_slots_locator,
                value=attribute_name
            )
        ]
        super().__init__(**data)


class RenameLinkMLElementOperation(CompoundOperation):
    old_name: str
    new_name: str
    container_path: str

    def __init__(self, /, **data: Any):
        old_name = data['old_name']
        new_name = data['new_name']
        container_path = data['container_path']
        data['inner_operations'] = [
            AddOperation(
                locator=make_jsonpath(f'{container_path}["{old_name}"].name'),
                value=new_name
            ),
            MoveOperation(
                locator=make_jsonpath(f'{container_path}["{old_name}"]'),
                target_locator=make_jsonpath(f'{container_path}["{new_name}"]'),
                constraint_strategy=PairwisePointerPairConstraintResolver()
            )
        ]
        data['locator'] = make_jsonpath('$')
        super().__init__(**data)


class RenameClassOperation(RenameLinkMLElementOperation):
    def __init__(self, /, **data: Any):
        data['container_path'] = '$.classes'
        super().__init__(**data)


class RenameSlotOperation(RenameLinkMLElementOperation):
    def __init__(self, /, **data: Any):
        data['container_path'] = '$.slots'
        super().__init__(**data)


class RenameAttributeOperation(RenameLinkMLElementOperation):
    class_name: str

    def __init__(self, /, **data: Any):
        class_name = data['class_name']
        data['container_path'] = f'$.classes["{class_name}"].attributes'
        super().__init__(**data)

# def perform_auto_update(obj: Any, ):
#     _to_check = [
#         '$.classes[*].attributes[*].name'
#     ]
#     jp = jsonpath.compile(_to_check[0])
#
#     actual_pointer = JSONPointer.from_parts(['classes', 'demo', 'attributes', 'myAttrib', 'name'])
#
#     check = can_pointer_match_path(actual_pointer, jp)
#     handled_pointer_value_pairs = set()
#
#     for class_ in obj['classes'].values():
#         for attribute in class_['attributes'].values():
#             pass


class AssignSlotUriOperation(AddOperation):
    class_name: str | None
    slot_name: str
    slot_uri: str

    def __init__(self, /, **data: Any):
        class_name = data['class_name'] if 'class_name' in data else None
        slot_name = data['slot_name']
        slot_uri = data['slot_uri']
        if class_name is None:
            data['locator'] = make_jsonpath(f'$.slots["{slot_name}"].slot_uri')
        else:
            if class_name == '*':
                data['locator'] = make_jsonpath(f'$.classes.*.attributes["{slot_name}"].slot_uri')
            else:
                data['locator'] = make_jsonpath(f'$.classes["{class_name}"].attributes["{slot_name}"].slot_uri')
        data['value'] = slot_uri
        data['class_name'] = class_name
        super().__init__(**data)


class AssignClassUriOperation(AddOperation):
    class_name: str
    class_uri: str

    def __init__(self, /, **data: Any):
        class_name = data['class_name']
        class_uri = data['class_uri']

        data['locator'] = make_jsonpath(f'$.classes["{class_name}"].class_uri')
        data['value'] = class_uri
        super().__init__(**data)


class AddPrefixesOperation(CompoundOperation):
    prefixes: dict[str, str]

    def __init__(self, /, **data: Any):
        prefixes = data['prefixes']

        data['locator'] = make_jsonpath(f'$')
        data['inner_operations'] = [
            AddOperation(
                locator=make_jsonpath(f'$.prefixes["{prefix_name}"]'),
                value=dict(
                    prefix_prefix=prefix_name,
                    prefix_reference=prefix_uri
                )
            )
            for prefix_name, prefix_uri in prefixes.items()
        ]
        super().__init__(**data)


class AssignUnitOperation(AddOperation):
    class_name: str
    attribute_name: str
    unit: Unit

    def __init__(self, /, **data: Any):
        unit = data['unit']
        linkml_unit = fetch_unit_object_from_qudt_unit_iri(tuple([unit['id']]))[0]
        class_name = data['class_name']
        attribute_name = data['attribute_name']
        data['locator'] = make_jsonpath(f'$.classes["{class_name}"].attributes["{attribute_name}"].unit')
        data['value'] = as_dict(linkml_unit)
        super().__init__(**data)


class AnnotateElementOperation(CompoundOperation):
    annotations: list[OntologicalAnnotation]

    def __init__(self, /, **data: Any):
        annotations = data.get('annotations', [])
        base_locator = data.get('locator')

        url_per_operator = collections.defaultdict(list)
        for annotation in annotations:
            operator = annotation['operator']
            url = annotation['iri']
            url_per_operator[operator].append(url)

        inner_operations = []
        for operator, url_list in url_per_operator.items():
            inner_operations.append(AddOperation(
                locator=make_jsonpath(f'{base_locator}.{operator}s'),
                value=url_list
            ))
        data['inner_operations'] = inner_operations
        data['annotations'] = [
            OntologicalAnnotation.model_validate(x)
            for x in annotations
        ]

        super().__init__(**data)





class AnnotateClassOperation(AnnotateElementOperation):

    class_name: str

    def __init__(self, /, **data: Any):
        class_name = data.get('class_name')
        data['locator'] = make_jsonpath(f'$.classes["{class_name}"]')
        super().__init__(**data)


class AnnotateAttributeOperation(AnnotateElementOperation):

    class_name: str
    attribute_name: str

    def __init__(self, /, **data: Any):
        class_name = data.get('class_name')
        attribute_name = data.get('attribute_name')
        data['locator'] = make_jsonpath(f'$.classes["{class_name}"].attributes["{attribute_name}"]')
        super().__init__(**data)



class CreateElementOperation(Operation, AddRegistrationMixin):

    element_name: str
    base_pointer: JSONPointer
    locator: PydanticJSONPath = make_jsonpath('$')  # This class does not use locator but has a more direct transformation
    fields: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, /, **data: Any):
        # element_name = data['element_name']
        super().__init__(**data)

    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):

        add_pointer = self.base_pointer / escape_json_pointer_part(self.element_name)

        patch_runner.add(add_pointer, {
            "name": self.element_name,
            **self.fields
        })


class CreateClassOperation(CreateElementOperation):
    class_name: str

    def __init__(self, /, **data: Any):
        class_name = data.get('class_name')
        data['base_pointer'] = JSONPointer('/classes')
        data['element_name'] = class_name
        fields = data.get('fields', {})
        if 'attributes' not in fields:
            fields['attributes'] = {}
        if 'slots' not in fields:
            fields['slots'] = []
        data['fields'] = fields
        super().__init__(**data)


class CreateAttributeOperation(CreateElementOperation):
    class_name: str
    attribute_name: str
    def __init__(self, /, **data: Any):
        class_name = data.get('class_name')
        attribute_name = data.get('attribute_name')
        data['base_pointer'] = JSONPointer(f'/classes/{class_name}/attributes')
        data['element_name'] = attribute_name
        super().__init__(**data)

    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):

        attributes_path = make_jsonpath(f'$.classes["{self.class_name}"].attributes')
        match = attributes_path.match(document)
        if match is None:
            rank = 0
        else:
            rank = len(match.obj)

        self.fields['rank'] = rank
        return super().register_rfc_operations(document, patch_runner)


class CreateAttributesOperation(CompoundOperation):
    class_name: str
    attribute_names: list[str]

    def __init__(self, /, **data: Any):
        attribute_names = data.get('attribute_names')
        class_name = data.get('class_name')
        data['inner_operations'] = [
            CreateAttributeOperation(
                class_name=class_name,
                attribute_name=name
            )
            for name in attribute_names
        ]
        super().__init__(**data)



class ConvertAttributeToRelationOperationProducer(AutomatedOperationProducer):

    triggers: list[jsonpath.JSONPath] = [
        make_jsonpath('$.classes.*.attributes.*.name'),
        make_jsonpath('$.classes.*.name')  # we must also react on new classes
    ]
    regular_expressions: list[re.Pattern] = [re.compile(r'^.+$')]
    group_index: int = 0
    #
    # def __init__(self, /, **data: Any):
    #     super().__init__(**data)
    #

    @profile
    def run(self, document: Any, modified_pointers: list[JSONPointer], settings: OptimizationSettings) -> list[Operation]:

        if settings.prevent_structural_enhancement:
            # Structural changes are not allowed
            return []

        has_new_or_renamed_class = any(len(p.parts) == 3 for p in modified_pointers)

        class_names = set(jsonpath.findall('$.classes.*.name', document))
        operations = []

        # pointers_to_process = [
        #     p
        #     for p in modified_pointers
        #     if len(p.parts) == 5  # this is an attribute pointer
        # ]

        if has_new_or_renamed_class:
            pointers_to_process = [
                match.pointer()
                for match in make_jsonpath('$.classes.*.attributes.*.name').finditer(document)
            ]
        else:
            pointers_to_process = modified_pointers

        for pointer in pointers_to_process:
            attribute_name = str(pointer.resolve(document))
            matches = [
                re.match(exp, attribute_name)
                for exp in self.regular_expressions
            ]
            matches = [m for m in matches if m is not None]
            target_entity_names = [m.group(self.group_index) for m in matches]
            if target_entity_names:
                target_entity_names.sort(key=len, reverse=True)
                for target_entity_name in target_entity_names:
                    if target_entity_name in class_names:
                        if pointer.parts[1] == target_entity_name:
                            continue  # this does not apply for primary keys
                        operations.append(MoveAttributeToRelationOperation(
                            locator=make_jsonpath(f'$.{'.'.join(pointer.parts[:-1])}'),
                            new_range=target_entity_name
                        ))
                        break
        return operations


class SimpleUnitAnnotationProducer(AutomatedOperationProducer):

    triggers: list[JSONPath] = [make_jsonpath('$.classes.*.attributes.*.name')]
    regular_expression: re.Pattern = re.compile(r'.+', re.IGNORECASE)
    unit_group_index: int = 0
    unit_iris: tuple[str, ...]
    fragment_whitelist: set[str]

    def run(self, document: Any, modified_pointers: list[JSONPointer], settings: dict[str, Any]) -> list[Operation]:
        operations = []
        for pointer in modified_pointers:
            unit_pointer = JSONPointer.from_parts(pointer.parts[:-1] + ('unit',), unicode_escape=False)
            if unit_pointer.resolve(document, default=None) is not None:
                # skip this pointer if it already has a unit
                continue

            attribute_name = str(pointer.resolve(document))
            match = re.search(self.regular_expression, attribute_name)
            if match is not None:
                unit_string = match.group(self.unit_group_index)
                if unit_string in self.fragment_whitelist:
                    unit_iri = find_best_matching_unit_for_text(self.unit_iris, unit_string)
                    if unit_iri is not None:
                        units = fetch_unit_object_from_qudt_unit_iri(tuple([unit_iri]))
                        if units:
                            unit = units[0]
                            locator = convert_pointer_to_path(unit_pointer)
                            operations.append(AddOperation(
                                locator=locator,
                                value=asdict(unit)
                            ))
        return operations


class StripUnitAndAnnotateFromSlot(AutomatedOperationProducer):

    triggers: list[JSONPath] = [make_jsonpath('$.classes.*.attributes.*.name')]
    regular_expression: re.Pattern = re.compile(r'(.+) *\[(.+)]', re.IGNORECASE)
    resulting_name_group_index: int = 1
    unit_group_index: int = 2

    # @staticmethod
    # def get_qudt_for_unit_string(unit_string: str) -> str | None:
    #     # TODO unit lookup via API
    #     if unit_string == '°':
    #         return 'https://qudt.org/degree'
    #     return None
    #
    # @staticmethod
    # def build_unit_object_from_qudt_url(url: str) -> UnitOfMeasure:
    #     # TODO resolve stuff from URL?
    #     return UnitOfMeasure(
    #
    #     )

    @profile
    def run(self, document: Any, modified_pointers: list[JSONPointer], settings: OptimizationSettings) -> list[Operation]:

        # unit_query_bind = """
        # PREFIX qudt: <http://qudt.org/schema/qudt/>
        #
        # SELECT ?unit
        # WHERE {
        #     ?unit a qudt:Unit ;
        #         qudt:symbol ?symbol .
        #     FILTER regex(?symbol, ?symbol_literal, "i")
        #     BIND ("C" as ?symbol_literal)
        # }
        # """
        #
        # unit_query_format_string = """
        # SELECT ?unit ?symbol
        # WHERE {{
        #     {value_mapping_string}
        #     ?unit a qudt:Unit ;
        #         qudt:symbol ?symbol .
        #     FILTER regex(?symbol, ?symbol_literal, "i")
        # }}
        # """
        #
        # value_mapping_string = "VALUES ( ?symbol_literal ) {{ {symbol_format_string}  }}"
        #
        #
        # unit_query = """
        # SELECT ?unit ?symbol
        # WHERE {
        #     ?unit a qudt:Unit ;
        #         qudt:symbol ?symbol .
        #     FILTER regex(?symbol, ?symbol_literal, "i")
        # }
        # """
        #
        #
        # unit_query_service = """
        #
        # SELECT ?unit
        # WHERE {
        #     SERVICE <https://www.qudt.org/fuseki/qudt/query> {
        #         ?unit a qudt:Unit ;
        #             # 	?p ?o .
        #             qudt:symbol ?symbol .
        #         # FILTER regex(?symbol, "C")
        #         # FILTER(?symbol = "°C"^^xsd:string)
        #         FILTER regex(?symbol, ?symbol_literal, "i")
        #     }
        # }
        # """
        #
        # query_endpoint = "https://www.qudt.org/fuseki/qudt/query"
        #
        # store = rdflib.plugins.stores.sparqlstore.SPARQLStore(query_endpoint)
        # graph = rdflib.Graph(store)
        #
        #
        #
        #
        # # sparql = SPARQLWrapper(query_endpoint)
        # # sparql.setReturnFormat(JSON)
        # # sparql.setQuery(unit_query_bind)
        # # result = sparql.query().convert()
        #
        # namespaces = {
        #     'xsd': rdflib.XSD,
        #     'qudt': rdflib.Namespace('http://qudt.org/schema/qudt/')
        # }
        #
        # prepared_service_query = rdflib.plugins.sparql.prepareQuery(unit_query_service, initNs={
        #     'xsd': rdflib.XSD,
        #     'qudt': rdflib.Namespace('http://qudt.org/schema/qudt/'),
        # })
        # # prepared_query = rdflib.plugins.sparql.prepareQuery(unit_query, initNs={
        # #     'xsd': rdflib.XSD,
        # #     'qudt': rdflib.Namespace('http://qudt.org/schema/qudt/'),
        # # })
        #
        #


        operations = []
        for pointer in modified_pointers:

            unit_pointer = JSONPointer.from_parts(pointer.parts[:-1] + ('unit',), unicode_escape=False)
            if unit_pointer.resolve(document, default=None) is not None:
                # skip this pointer if it already has a unit
                continue

            class_name = pointer.parts[-4]
            attribute_name = str(pointer.resolve(document))
            match = re.match(self.regular_expression, attribute_name)
            if match is not None:
                target_entity_name = match.group(self.resulting_name_group_index)


                unit_string = match.group(self.unit_group_index)

                # unit_symbol_literal = rdflib.Literal(unit_string)
                url = search_unit_iri_by_symbol(unit_string)

                # value_mapping = value_mapping_string.format(
                #     symbol_format_string=' '.join([f'( "{var}" )' for var in [unit_symbol_literal]])
                # )
                # query = unit_query_format_string.format(value_mapping_string=value_mapping)
                #
                # result = graph.query(query, initNs=namespaces)
                #
                # test = list(result)
                # distances = [
                #     Levenshtein.distance(x[1], unit_string)
                #     for x in test
                # ]

                # result = graph.query(prepared_query, initBindings={'symbol_literal': unit_symbol_literal})

                # url = self.get_qudt_for_unit_string(unit_string)
                if url is not None:

                    # unit = self.build_unit_object_from_qudt_url(url)
                    units = fetch_unit_object_from_qudt_unit_iri(tuple([url]))
                    if units:
                        unit = units[0]
                        locator = convert_pointer_to_path(unit_pointer)
                        operations.append(AddOperation(
                            locator=locator,
                            value=asdict(unit)
                        ))
                    if not settings.prevent_structural_enhancement:
                        # Changing the name of an attribute is a structural change so prevent it if requested
                        if target_entity_name != attribute_name:
                            operations.append(RenameAttributeOperation(
                                class_name=class_name,
                                old_name=attribute_name,
                                new_name=target_entity_name
                            ))
        return operations


class ResolveSegmentationOfClassesProducer(AutomatedOperationProducer):

    class_name_filter_regex: re.Pattern = re.compile('.*')
    on_group_rename_source_regex: re.Pattern | None = None
    on_group_rename_replace_regex: str | None = None
    triggers: list[JSONPath] = [make_jsonpath('$.classes.*.attributes.*.name')]

    @profile
    def run(self, document: Any, modified_pointers: list[JSONPointer], settings: OptimizationSettings) -> list[Operation]:
        if settings.prevent_structural_enhancement:
            return []  # Segmentation is a structural enhancement so skip it entirely
        operations = []
        class_names: set[str] = set(jsonpath.findall('$.classes.*.name', document))
        attribute_set_class_lookup = collections.defaultdict(list)
        for class_name in class_names:
            if re.match(self.class_name_filter_regex, class_name) is not None:
                attribute_names = frozenset(jsonpath.findall(f'$.classes["{class_name}"].attributes.*.name', document))
                attribute_set_class_lookup[attribute_names].append(class_name)

        for attribute_set, groupable_class_names in attribute_set_class_lookup.items():
            if len(groupable_class_names) > 1:
                if self.on_group_rename_source_regex is not None:
                    target_name = re.sub(
                        self.on_group_rename_source_regex,
                        self.on_group_rename_replace_regex,
                        groupable_class_names[0]
                    )
                else:
                    target_name = groupable_class_names[0]
                if target_name != groupable_class_names[0]:
                    operations.append(RenameClassOperation(
                        old_name=groupable_class_names[0],
                        new_name=target_name
                    ))

                operations.extend([
                    RemoveOperation(locator=make_jsonpath(f'$.classes["{name}"]'))
                    for name in groupable_class_names[1:]
                ])

                operations.append(AddOperation(
                    user_preconditions=[
                        Precondition(
                            query=make_jsonpath(f'$.classes["{target_name}"].extensions.segmentation'),
                            function=DoesNotExistPreconditionFunction()
                        )
                    ],
                    locator=make_jsonpath(f'$.classes["{target_name}"].extensions.segmentation'),
                    value={
                        "tag": "segmentation",
                        "value": {
                            "segments_added": []
                        }
                    }
                ))

                operations.extend([
                    AddOperation(
                        locator=make_jsonpath(f'$.classes["{target_name}"].extensions.segmentation.value.segments_added[-1]'),
                        value=name
                    )
                    for name in groupable_class_names[1:]
                ])
        if operations:
            return [CompoundOperation(inner_operations=operations)]
        return []


class DetectRelationOperationProducer(AutomatedOperationProducer):

    def run(self, document: Any, modified_pointers: list[JSONPointer], settings: dict[str, Any]) -> list[Operation]:
        pass