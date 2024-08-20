import collections
import functools
import sys
from tempfile import TemporaryDirectory
from typing import List, Dict, Tuple, Iterable, Callable, Any, Iterator
import urllib.parse
from zipfile import ZipFile

import lxml.etree
from xmlschema import XMLSchema11, XsdElement, XsdComponent, XMLSchemaBase, XMLSchemaValidationError
import xmlschema.validators
from xmlschema.validators import (XsdComplexType, XsdUnique, XsdKey, XsdKeyref, XsdAttribute,
                                  Xsd11Unique, Xsd11Element, XsdSimpleType, Xsd11AtomicRestriction,
                                  XsdAtomicRestriction, XsdAtomicBuiltin)

from simpler_core.cardinality import create_cardinality
from simpler_core.plugin import DataSourcePlugin, DataSourceType, InputDataError
from simpler_core.schema import make_hierarchical_name, is_hierarchical_path, split_prefix_and_item_name

try:
    from simpler_model import Relation, Entity, Attribute, EntityModifier, Cardinality, RelationModifier, \
        AttributeModifier

    EntityLink = Relation
except ImportError:
    from simpler_model import Entity, Attribute, EntityLink

# TODO there are several types of "standard" XML description languages that we should all support:
#  DTD, XSD, RelaxNG and Schematron


class EnhancedXsdElement:
    def __init__(self, xsd_element: XsdElement, parent: 'EnhancedXsdElement' = None):
        self.xsd_element = xsd_element
        self.parent = parent
        self.child_blacklist = set()

    @property
    def path(self) -> str:
        prefix = f'{self.parent.path}' if self.parent is not None else ''
        return f'{prefix}/{self.xsd_element.prefixed_name}'

    @property
    def children(self) -> Iterator['EnhancedXsdElement']:
        for child in self.xsd_element:
            if isinstance(child, XsdElement):
                enhanced_child = EnhancedXsdElement(child, self)
                if enhanced_child.prefixed_name not in self.child_blacklist:
                    yield enhanced_child

    def __getattr__(self, item):
        if item in {'xsd_element', 'path', 'parent', 'children', 'child_blacklist'}:
            return getattr(self, item)
        return getattr(self.xsd_element, item)

    def __repr__(self):
        return f'{self.path} => {self.xsd_element.__repr__()}'


def full_flattener(
        roots: List[EnhancedXsdElement],
        max_depth=10,
        filter_function=lambda x: True
) -> Iterator[EnhancedXsdElement]:
    for root in roots:
        yield from tree_flattener(root, max_depth, filter_function)


def tree_flattener(
        element: EnhancedXsdElement,
        max_depth=10,
        filter_function=lambda x: True
) -> Iterator[EnhancedXsdElement]:
    depth = element.path.count('/')
    if depth < max_depth and filter_function(element):
        yield element
        for child in element.children:
            yield from tree_flattener(child, max_depth, filter_function)


def is_primitive_element(element: EnhancedXsdElement | XsdElement) -> bool:
    # it seems the content as XsdSimpleType is not a primitive because it still could be complex (e.g. having attrs)
    return isinstance(element.type, (XsdAtomicRestriction, XsdAtomicBuiltin, XsdSimpleType))  # or \
    # isinstance(element.type.content, XsdSimpleType)


def find_all_elements_recursively_enhanced(
    element: EnhancedXsdElement,
    elements: List[EnhancedXsdElement] = None
) -> List[EnhancedXsdElement]:
    if elements is None:
        elements = []

    path_depth = element.path.count('/')
    if path_depth >= 10:
        return elements
    if not is_primitive_element(element):
        elements.append(element)
        for child in element.children:
            find_all_elements_recursively_enhanced(child, elements)
    return elements


def find_all_elements_recursively(
    element: XsdElement,
    base_path: str = '',
    # visited_paths: Set[str] = None,
    elements: Dict[str, XsdElement] = None
) -> Dict[str, XsdElement]:
    # if visited_paths is None:
    #     visited_paths = set()
    if elements is None:
        elements = dict()

    path = f'{base_path}/{element.prefixed_name}'
    path_depth = path.count('/')
    if path_depth >= 10:
        return elements
    if path not in elements:
        if not is_primitive_element(element):
            # visited_paths.add(path)
            elements[path] = element
            for child in element:
                if isinstance(child, XsdElement):
                    # find_all_elements_recursively(child, path, visited_paths, elements)
                    find_all_elements_recursively(child, path, elements)

    return elements


def cardinality_factory_single(occurs: Tuple) -> Cardinality:
    occurs = tuple(
        int(x) if x is not None else sys.maxsize
        for x in occurs
    )
    return create_cardinality(occurs)


def build_attributes_and_related_entities_enhanced(
        path: str,
        element: EnhancedXsdElement
) -> Tuple[List[Attribute], List[Relation]]:
    attributes = []
    related_entities = []
    quoted_path = urllib.parse.quote(path, safe='')

    for attribute_key in [x for x in element.attributes if x is not None]:
        attributes.append(Attribute(
            attribute_name=[attribute_key],
            has_attribute_modifier=None
        ))
        # attribute_obj = element.attributes[attribute_key].type
        # TODO if the attribute is of type "xs:IDREFS" (plural) this actually means a whitespace separated list of ids.
        #  In that scenario we should at least set isCollection (or future cardinalities) to True. Maybe we even need
        #  to create a sub-entity?

    try:
        if isinstance(element.type.content, XsdSimpleType):
            attributes.append(Attribute(
                attribute_name=['value'],
                has_attribute_modifier=None
            ))
    except:
        pass

    def cardinality_factory(occurs: Tuple) -> List[str]:
        cardinality = [
            str(x) if x is not None else 'n'
            for x in occurs
        ]
        if cardinality == ['n', 'n']:
            cardinality = ['n', 'm']
        return cardinality

    def extract_attribute_occurrence(attribute: XsdAttribute) -> Tuple[int, int]:
        min_occur = 0
        max_occur = 1
        if attribute.use == 'required':
            min_occur = 1
        if attribute.type.display_name == 'xs:IDREFS':
            max_occur = None
        return min_occur, max_occur

    def unify_occurrences(occurrences: List[Tuple[int, int]]) -> Tuple[int, int]:
        minimums, maximums = list(zip(*occurrences))
        min_occurrence = max(minimums)
        max_occurrence = None if None in maximums else min(maximums)
        return min_occurrence, max_occurrence

    for child in element.children:
        quoted_child_path = urllib.parse.quote(child.path, safe='')
        if is_primitive_element(child):
            attributes.append(Attribute(
                attribute_name=[child.prefixed_name],
                has_attribute_modifier=None
            ))
        else:
            related_entities.append(Relation(
                relation_name=['IsChild'],
                # has_object_entity=f'{quoted_child_path}',
                has_object_entity=f'{child.path[1:]}',
                # has_subject_entity=f'{quoted_path}',
                has_subject_entity=f'{path[1:]}',
                object_cardinality=cardinality_factory_single(child.occurs),
                subject_cardinality=cardinality_factory_single((1, 1)),
                has_attribute=[],
                has_relation_modifier=[RelationModifier(relation_modifier='identifying')]
            ))

    for reference in sorted(element.selected_by, key=lambda x: 0 if isinstance(x, XsdKey) else 1):
        if isinstance(reference, XsdKeyref):
            target_element = next(iter(reference.refer.elements.keys()))
            field_objects = [
                element.xpath_proxy.find(f'{element.path}/{field.path}')  # TODO this probably fails with a non-local field path
                for field in reference.fields
            ]

            # Remove the "foreign keys" from the attribute unless they are no primary key
            attributes_to_remove = []
            for field in field_objects:
                for attribute in attributes:
                    if field.name == attribute.attribute_name[0] and not (
                            attribute.has_attribute_modifier and
                            attribute.has_attribute_modifier[0].attribute_modifier == 'key'):
                        attributes_to_remove.append(attribute)
            for attribute in attributes_to_remove:
                attributes.remove(attribute)

            field_occurs = [
                extract_attribute_occurrence(field) if isinstance(field, XsdAttribute) else field.occurs
                for field in field_objects
            ]
            field_occur = unify_occurrences(field_occurs)
            encoded_name = urllib.parse.quote(target_element.prefixed_name, safe='')
            related_entities.append(Relation(
                relation_name=[reference.prefixed_name],
                # has_object_entity=f'{encoded_name}',
                has_object_entity=f'{target_element.prefixed_name}',
                # has_subject_entity=f'{quoted_path}',
                has_subject_entity=f'{path[1:]}',
                object_cardinality=cardinality_factory_single(field_occur),
                subject_cardinality=cardinality_factory_single((0, None)),
                has_attribute=[],
                has_relation_modifier=[]
            ))
        elif isinstance(reference, XsdKey):
            field_objects = [
                element.xpath_proxy.find(f'{element.path}/{field.path}')
                # TODO this probably fails with a non-local field path
                for field in reference.fields
            ]
            for field in field_objects:
                for attribute in attributes:
                    if attribute.attribute_name[0] == field.name:
                        attribute.has_attribute_modifier = [AttributeModifier(attribute_modifier='key')]

    return attributes, related_entities


# def build_attributes_and_related_entities(
#         path: str,
#         element: XsdElement
# ) -> Tuple[List[Attribute], List[EntityLink]]:
#     attributes = []
#     related_entities = []
#
#     mapper = {
#         'Xsd11Key': 'XsdKey',
#         'Xsd11Unique': 'XsdUnique',
#         'Xsd11Keyref': 'XsdKeyref'
#     }
#
#     def _mapper(name_in: str) -> str:
#         if name_in in mapper:
#             return mapper[name_in]
#         return name_in
#
#     relations = {
#         _mapper(type(x).__name__): x
#         for x in element.selected_by
#     }
#
#     for attribute_key in [x for x in element.attributes if x is not None]:
#
#         # if attribute_key in local_attribute_key_lookup:
#         #     x = 42
#         # if attribute_key in local_attribute_key_refs_lookup:
#         #     x = 42
#         # if attribute_key in local_attribute_unique_lookup:
#         #     x = 42
#         # TODO handle key creation
#         attributes.append(Attribute(
#             name=[attribute_key],
#             type='string',  # TODO if an xsd or dtd is available we could make this more precise
#             is_collection=False
#         ))
#         # attribute_obj = element.attributes[attribute_key].type
#         # TODO if the attribute is of type "xs:IDREFS" (plural) this actually means a whitespace separated list of ids.
#         #  In that scenario we should at least set isCollection (or future cardinalities) to True. Maybe we even need
#         #  to create a sub-entity?
#
#     try:
#         if isinstance(element.type.content, XsdSimpleType):
#             attributes.append(Attribute(
#                 name='value',
#                 type='string',
#                 isCollection=False
#             ))
#     except:
#         pass
#
#     children = [x for x in element if isinstance(x, XsdElement)]
#     for child in children:
#         child_path = f'{path}/{child.prefixed_name}'
#         quoted_child_path = urllib.parse.quote(child_path, safe='')
#         if is_primitive_element(child):
#             attributes.append(Attribute(
#                 name=child.prefixed_name,
#                 type='string',  # TODO again check if we can get the type from xsd or dtd
#                 isCollection=child.max_occurs is None or child.max_occurs > 1
#             ))
#         else:
#             related_entities.append(EntityLink(
#                 name=child_path[1:],
#                 link=f'http://localhost:7373/schemata/iec61850/entities/{quoted_child_path}',
#             ))
#
#     return attributes, related_entities


def group_by(
        iterable: Iterable[Any],
        key_function: Callable[[Any], Any],
        value_function: Callable[[Any], Any] = lambda x: x
) -> Dict[Any, List[Any]]:
    result = collections.defaultdict(list)
    for item in iterable:
        result[key_function(item)].append(value_function(item))
    return result


class XmlDataSourceType(DataSourceType):
    name = 'XML'
    inputs = ['data', 'xsd', 'dtd', 'xsd_extra', 'custom_spec']


class XmlDataSourcePlugin(DataSourcePlugin):

    data_source_type = XmlDataSourceType()

    @staticmethod
    def _build_data_only_schema(root: lxml.etree._Element):

        # url_prefix = 'http://localhost:7373/schemata/iec61850/entities/'

        def is_simple_node(element: lxml.etree._Element) -> bool:
            if len(element.attrib) != 0:
                return False
            for child in element:
                if isinstance(child, lxml.etree._Element):
                    return False
            return True

        # def path_builder(entity: Entity) -> str:
        #     if entity is None:
        #         return ''
        #     return urllib.parse.unquote(entity.url[len(url_prefix):])

        def recurse_tree(start: lxml.etree._Element, parent: Entity = None, entities: Dict[str, List[Entity]] = None) -> Dict[str, List[Entity]]:
            if entities is None:
                entities = collections.defaultdict(list)
            # parent_path = path_builder(parent)
            parent_path = parent.entity_name[0] if parent is not None else None
            siblings = entities[parent_path]

            # parent_path_with_slash = f'{parent_path}/' if parent_path else ''
            active_item_name = start.tag
            # active_item_path = f'{parent_path_with_slash}{active_item_name}'
            active_item_path = make_hierarchical_name(parent_path, active_item_name)
            # active_item_quoted_path = urllib.parse.quote(active_item_path, safe='')
            existing_spec: Entity | Attribute | None = None
            for sibling in siblings:
                if sibling.entity_name[0] == active_item_path[1:]:
                    existing_spec = sibling
                    break
            if existing_spec is None and parent is not None:
                for attribute in parent.has_attribute:
                    if attribute.attribute_name[0] == active_item_name:
                        existing_spec = attribute
                        break

            if is_simple_node(start):
                if parent is not None:
                    if existing_spec is None:
                        attribute = Attribute(
                            attribute_name=[active_item_name],
                            has_attribute_modifier=None
                        )
                        parent.has_attribute.append(attribute)
                    # At this point there could be already an attribute with that name or even an entity - in both
                    #  cases we stick with the previous instance
                else:
                    # this obviously implies that existing_spec is also None so no special treatment needed
                    entities[''].append(Entity(
                        entity_name=[active_item_path[1:]],
                        has_attribute=[],
                        has_entity_modifier=[
                            EntityModifier(entity_modifier='weak')
                        ] if is_hierarchical_path(active_item_path) else None,
                        is_object_in_relation=None,
                        is_subject_in_relation=[]

                        # url=f'{url_prefix}{active_item_path}',
                        # name=active_item_path,
                        # type='strong',
                        # attributes=[],
                        # related_entities=[],
                        # key=None
                    ))
            else:
                new_entity = None
                if isinstance(existing_spec, Attribute):
                    # This can either mean this attribute is sometimes simple and sometimes complex, or we do have
                    #  an attribute and a child tag with the same name. This needs we need to check the parent for an
                    #  actual attribute of that name. We would have found the child tag first so we don't need to worry
                    xml_parent: lxml.etree._Element = start.getparent()
                    if active_item_name not in xml_parent.attrib:
                        # this was therefore a simple child before - replace it with the complex one
                        parent.has_attribute.remove(existing_spec)

                    # at this point we do either have a child and a tag with the same name or, a child that is
                    #  sometimes simple and sometimes not - in that case the simple one was just removed
                    new_entity = Entity(
                        entity_name=[active_item_path[1:]],
                        has_attribute=[],
                        has_entity_modifier=[
                            EntityModifier(entity_modifier='weak')
                        ] if is_hierarchical_path(active_item_path) else None,
                        is_object_in_relation=[],
                        is_subject_in_relation=[]

                        # url=f'{parent.url}%2F{active_item_path}',
                        # name=active_item_path,
                        # type='weak',
                        # attributes=[],
                        # related_entities=[],
                        # key=None
                    )
                    parent.is_subject_in_relation.append(Relation(
                        relation_name=['IsChild'],
                        has_object_entity=new_entity.entity_name[0],
                        has_subject_entity=f'{active_item_path[1:]}',
                        object_cardinality=create_cardinality((0, sys.maxsize)),
                        subject_cardinality=cardinality_factory_single((1, 1)),
                        has_attribute=[],
                        has_relation_modifier=[]
                    ))
                elif isinstance(existing_spec, Entity):
                    # at the moment the only thing that can differ is the attributes - so let's check them
                    new_attribute_names = set(start.attrib.keys())
                    old_attribute_names = set(x.attribute_name[0] for x in existing_spec.has_attribute)
                    attribute_names_to_add = (new_attribute_names ^ old_attribute_names) & new_attribute_names
                    for name in attribute_names_to_add:
                        existing_spec.has_attribute.append(Attribute(
                            attribute_name=[name],
                            has_attribute_modifier=None
                        ))
                else:
                    # no existing spec
                    if parent is not None:
                        new_entity = Entity(
                            entity_name=[active_item_path[1:]],
                            has_attribute=[],
                            has_entity_modifier=[
                                EntityModifier(entity_modifier='weak')
                            ] if is_hierarchical_path(active_item_path) else None,
                            is_object_in_relation=[],
                            is_subject_in_relation=[]

                            # url=f'{url_prefix}{active_item_quoted_path}',
                            # name=active_item_path,
                            # type='weak',
                            # attributes=[],
                            # related_entities=[],
                            # key=None
                        )
                        parent.is_subject_in_relation.append(Relation(
                            relation_name=['IsChild'],
                            has_object_entity=new_entity.entity_name[0],
                            has_subject_entity=f'{active_item_path[1:]}',
                            object_cardinality=create_cardinality((0, sys.maxsize)),
                            subject_cardinality=cardinality_factory_single((1, 1)),
                            has_attribute=[],
                            has_relation_modifier=[]
                        ))
                    else:
                        # this seems to be the root
                        new_entity = Entity(
                            entity_name=[active_item_path[1:]],
                            has_attribute=[],
                            has_entity_modifier=[
                                EntityModifier(entity_modifier='weak')
                            ] if is_hierarchical_path(active_item_path) else None,
                            is_object_in_relation=[],
                            is_subject_in_relation=[]

                            # url=f'{url_prefix}{active_item_quoted_path}',
                            # name=active_item_path,
                            # type='strong',
                            # attributes=[],
                            # related_entities=[],
                            # key=None
                        )
                if new_entity is not None:
                    for key, _ in start.attrib.items():
                        new_entity.has_attribute.append(Attribute(
                            attribute_name=[key],
                            has_attribute_modifier=None
                        ))

                    entities[parent_path].append(new_entity)

                # we iterate children in any case we might find different
                #  representations in other children of the same kind
                next_parent = new_entity if new_entity is not None else existing_spec
                for child in start:
                    recurse_tree(child, next_parent, entities)
            return entities
        return recurse_tree(root)

    @staticmethod
    def _generate_xsd_schema(schema: XMLSchema11, data_root: lxml.etree._Element) -> Dict[str, List[Entity]]:
        # it seems some schemas do have more than one root element - which means we probably need to find the real root
        #  from data
        # if len(schema.root_elements) != 1:
        #     raise RuntimeError('It seems the schema has multiple roots')
        # instance_root_schema = schema.root_elements[0]  # type: XsdElement
        instance_root_schema = \
            [EnhancedXsdElement(x) for x in schema.root_elements if x.prefixed_name == data_root.tag][0]

        if instance_root_schema.occurs != (1, 1):
            raise RuntimeError('The schema root seems to allow something else than exactly one root')

        # It seems findall does in fact not find all the elements - we will need a path based deep-search instead
        # all_elements = schema.findall('//*')

        # all_elements_new = find_all_elements_recursively_enhanced(instance_root_schema)
        # TODO investigate if the recursive search does also find the entities of potential values for attributes -
        #  do we even need that?

        custom_root_elements = []

        # the following contains a dict that is not reliant on the iterator anymore - the objects however should be refs
        elements_grouped_by_tag = group_by(tree_flattener(instance_root_schema), lambda x: x.prefixed_name)
        additions: List[EnhancedXsdElement] = []
        removals: List[EnhancedXsdElement] = []
        for tag, group in elements_grouped_by_tag.items():
            keys = set(
                reference
                for element in group
                for reference in element.selected_by
                if isinstance(reference, XsdKey)
            )
            if len(keys) > 0 and all(key in element.selected_by for element in group for key in keys):
                # All the occurring elements share the same key(s) -> we can merge them to be global (and strong?)
                additions.append(group[0])
                for element in group:
                    if element.parent is not None:
                        removals.append(element)

        for removal in sorted(removals, key=lambda x: x.path.count('/'), reverse=True):
            removal.parent.child_blacklist.add(removal.path.replace(removal.parent.path, '')[1:])

        for addition in additions:
            new_element = EnhancedXsdElement(addition.xsd_element)
            new_element.child_blacklist = addition.child_blacklist.copy()
            custom_root_elements.append(new_element)

        # component_lookup = collect_components_recursively(schema)
        #
        # component_mapping = {
        #     'Xsd11Key': 'key',
        #     'XsdKey': 'key',
        #     'Xsd11Keyref': 'reference',
        #     'XsdKeyref': 'reference',
        #     'Xsd11Unique': 'unique',
        #     'XsdUnique': 'unique'
        # }
        #
        # custom_component_lookup = collections.defaultdict(list)
        # for source, target in component_mapping.items():
        #     custom_component_lookup[target].extend(component_lookup[source] if source in component_lookup else [])

        # return schema, all_elements_new, custom_component_lookup, data_root
        schema_roots = [instance_root_schema] + custom_root_elements

        entities = collections.defaultdict(list)
        # for path, element in elements.items():
        for element in full_flattener(schema_roots, filter_function=lambda x: not is_primitive_element(x)):
            path = element.path
            quoted_path = urllib.parse.quote(path, safe='')
            name = path[1:]
            quoted_element_name = urllib.parse.quote(element.prefixed_name, safe='')
            # if entity_prefix == '*' or path == f'{entity_prefix}/{element.prefixed_name}':
            entity = Entity(
                entity_name=[name],
                has_attribute=[],
                has_entity_modifier=None if '/' not in name else [EntityModifier(entity_modifier='weak')],
                is_object_in_relation=None,
                is_subject_in_relation=None
            )
            attributes, related_entities = build_attributes_and_related_entities_enhanced(path, element)
            entity.has_attribute = attributes
            entity.is_subject_in_relation = related_entities
            # prefix, element_name = f'/{path}'.rsplit('/', maxsplit=1)
            prefix, element_name = path.rsplit('/', maxsplit=1)
            entities[prefix[1:]].append(entity)

        return entities

    def _generate_model(self, name: str) -> Dict[str, List[Entity]]:
        schema = None
        dtd = None
        data_tree: lxml.etree.ElementTree = None
        data_root: lxml.etree._Element = None

        with self.storage.get_data(name) as stream_lookup, TemporaryDirectory() as extra_directory:
            if 'xsd_extra' in stream_lookup:
                with ZipFile(stream_lookup['xsd_extra']) as extra_zip:
                    extra_zip.extractall(extra_directory)
            if 'xsd' in stream_lookup:
                schema = XMLSchema11(stream_lookup['xsd'], base_url=extra_directory)
            if 'dtd' in stream_lookup:
                raise NotImplementedError('Support for dtd schemas has not been added yet')
            data_tree = lxml.etree.parse(stream_lookup['data'])
            data_root = data_tree.getroot()

        if schema is not None:
            try:
                # schema.validate(data_tree)  # comment out for performance reasons while debugging
                pass
            except XMLSchemaValidationError as ex:
                raise InputDataError("XML Validation failed") from ex

        if schema is None:
            return self._build_data_only_schema(data_root)
        return self._generate_xsd_schema(schema, data_root)

    def get_strong_entities(self, name: str) -> List[Entity]:
        entities = self._generate_model(name)
        return entities['']

    def get_all_entities(self, name: str) -> List[Entity]:
        entities = self._generate_model(name)
        return [x for inner in entities.values() for x in inner]

    def get_related_entity_links(self, name: str) -> List[Relation]:
        pass

    def get_entity_by_id(self, name: str, entity_id: str) -> Entity:
        entities = self._generate_model(name)
        prefix, _ = split_prefix_and_item_name(entity_id)
        # prefix, _ = f'/{entity_id}'.rsplit('/', maxsplit=1)
        # prefix = prefix[1:]
        subset = entities[prefix]
        for entity in subset:
            if entity_id in entity.entity_name:
                return entity
        raise KeyError('Entity ID cannot be resolved')
