import collections
import functools
import shelve
import sys
from typing import Any

import Levenshtein
import rdflib
import rdflib.plugins.sparql
import rdflib.plugins.sparql.sparql
import rdflib.plugins.stores.sparqlstore
from linkml_runtime.linkml_model.units import UnitOfMeasure
from rdflib import URIRef, Literal
from rdflib.namespace import split_uri

from fairlead_core.settings import Settings
from simpler_model import Unit

unit_graph: rdflib.Graph | None = None
coarse_unit_query: str | rdflib.plugins.sparql.sparql.Query | None = None
unit_details_query: str | rdflib.plugins.sparql.sparql.Query | None = None
unit_name_query: str | rdflib.plugins.sparql.sparql.Query | None = None
quantity_kind_query: str | rdflib.plugins.sparql.sparql.Query | None = None
enhanced_unit_query: str | rdflib.plugins.sparql.sparql.Query | None = None
combined_query: str | rdflib.plugins.sparql.sparql.Query | None = None
lookup_generation_query: str | rdflib.plugins.sparql.sparql.Query | None = None
simple_unit_query: str | rdflib.plugins.sparql.sparql.Query | None = None
get_term_strings_query: str | rdflib.plugins.sparql.sparql.Query | None = None
all_unit_query: str | None = None


def initialize_unit_lookup():
    settings = Settings()
    url = settings.unit_resolution_uri

    global unit_graph

    if url.startswith("http"):
        store = rdflib.plugins.stores.sparqlstore.SPARQLStore(url)
        unit_graph = rdflib.Graph(store)
    else:
        cache = shelve.open('unit_graph.cache')
        if 'unit_graph' in cache:
            unit_graph = cache['unit_graph']
        else:
            unit_graph = rdflib.Graph()
            unit_graph.parse(url)
            cache['unit_graph'] = unit_graph
        cache.close()

    global coarse_unit_query
    coarse_unit_query = """
    PREFIX qudt: <http://qudt.org/schema/qudt/>
    
    SELECT ?unit ?symbol
    WHERE {
        VALUES ( ?symbol_literal ) { <<symbol_lister_list>> }
        ?unit a qudt:Unit;
            qudt:symbol ?symbol .
        FILTER regex(?symbol, ?symbol_literal, "i")
    }
    """

    global enhanced_unit_query
    enhanced_unit_query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX soqk: <http://qudt.org/vocab/soqk/>
        PREFIX qudt: <http://qudt.org/schema/qudt/>

        SELECT ?unit (COALESCE(?symbol, ?label_en, ?label_nolang) AS ?unit_text) ?kind
        WHERE {
            VALUES ( ?fragment ) { <<fragments>> }
            ?unit a qudt:Unit ;
                 qudt:hasQuantityKind ?kind .
            soqk:SI (qudt:hasBaseQuantityKind | qudt:systemDerivedQuantityKind) ?kind .

            OPTIONAL { 
            	?unit rdfs:label ?label_en . 
            	FILTER( LANG(?label_en) = "en" ) 
            	FILTER regex(?label_en, ?fragment, "i")
        	}
            OPTIONAL {
            	?unit rdfs:label ?label_nolang .
            	FILTER( LANG(?label_nolang) = "" )
            	FILTER regex(?label_nolang, ?fragment, "i")
        	}

            OPTIONAL {
            	?unit qudt:symbol ?symbol .
            	FILTER regex(?symbol, ?fragment, "i")
        	}

            FILTER (
                BOUND(?symbol) ||
                BOUND(?label_en) ||
                BOUND(?label_nolang)
              )
        }
        """

    global quantity_kind_query
    quantity_kind_query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX soqk: <http://qudt.org/vocab/soqk/>
    PREFIX qudt: <http://qudt.org/schema/qudt/>
    
    SELECT ?kind (COALESCE(?symbol, ?label_en, ?label_nolang) AS ?kind_text)
    WHERE {
        VALUES ( ?fragment ) { <<fragments>> }
        ?kind a qudt:QuantityKind. 
        soqk:SI (qudt:hasBaseQuantityKind | qudt:systemDerivedQuantityKind) / qudt:exactMatch* ?kind .
        
        OPTIONAL { 
        	?kind rdfs:label ?label_en . 
        	FILTER( LANG(?label_en) = "en" ) 
        	FILTER regex(?label_en, ?fragment, "i")
    	}
        OPTIONAL {
        	?kind rdfs:label ?label_nolang .
        	FILTER( LANG(?label_nolang) = "" )
        	FILTER regex(?label_nolang, ?fragment, "i")
    	}
        
        OPTIONAL {
        	?kind qudt:symbol ?symbol .
        	FILTER regex(?symbol, ?fragment, "i")
    	}
        
        FILTER (
            BOUND(?symbol) ||
            BOUND(?label_en) ||
            BOUND(?label_nolang)
          )
    }
    """

    global unit_details_query
    unit_details_query = """
    PREFIX qudt: <http://qudt.org/schema/qudt/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?unit ?symbol ?abbreviation (COALESCE(?label_en, ?label_nolang) AS ?descriptive_name) ?ucum_code ?has_quantity_kind ?iec61360code ?dbpedia_match ?wikidata_match
    WHERE {
        VALUES ( ?unit ) { <<unit_iri>> }
        ?unit   qudt:symbol ?symbol .
                
        OPTIONAL { ?unit rdfs:label ?label_en . FILTER( LANG(?label_en) = "en" ) }
        OPTIONAL { ?unit rdfs:label ?label_nolang . FILTER( LANG(?label_nolang) = "" ) }
        # FILTER( (lang(?descriptive_name) = "en")  ||  (!(langMatches(lang(?descriptive_name),"*"))) )
        OPTIONAL { ?unit qudt:abbreviation ?abbreviation . }
        OPTIONAL { ?unit qudt:ucum_code ?ucum_code . }
        OPTIONAL { ?unit qudt:has_quantity_kind ?has_quantity_kind . }
        OPTIONAL { ?unit qudt:iec61360code ?iec61360code . }
        OPTIONAL { ?unit qudt:dbpediaMatch ?dbpedia_match . }
        OPTIONAL { ?unit qudt:wikidataMatch ?wikidata_match . }
    }
    """

    global unit_name_query
    unit_name_query = """
    PREFIX qudt: <http://qudt.org/schema/qudt/>
    
    SELECT ?unit
    WHERE {
        VALUES ( ?name ) { <<name>> }
        ?unit a qudt:Unit .
        FILTER regex(str(?unit), ?name, "i")
    }
    LIMIT <<limit>>
    """

    global simple_unit_query
    simple_unit_query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX qudt: <http://qudt.org/schema/qudt/>

SELECT DISTINCT ?iri ?text
WHERE {
  VALUES (?search_string) { <<fragments>>}

  {
    # 1) search string in the IRI itself (including fragment)
    BIND(STR(?iri) AS ?text)
    FILTER(CONTAINS(LCASE(?text), LCASE(?search_string)))
  }
  UNION
  {
    # 2) search string in rdfs:label
    ?iri rdfs:label ?text .
    FILTER(
      CONTAINS(LCASE(STR(?text)), LCASE(?search_string))
    )
  }
  UNION
  {
    # 3) search string in qudt:symbol
    ?iri qudt:symbol ?text .
    FILTER(
      CONTAINS(LCASE(STR(?text)), LCASE(?search_string))
    )
  }
}
    """

    # The following query is fast if executed on GraphDB (less than 1s for some fragment combos i tested)
    #  however, rdflib is a mess. It takes ~30min to solve this so I guess I will need to implement
    #  this with custom code instead
    global combined_query
    combined_query = """
    PREFIX qudt: <http://qudt.org/schema/qudt/>
    PREFIX soqk: <http://qudt.org/vocab/soqk/>

    SELECT DISTINCT ?unit ?unit_text ?kind ?kind_text
    WHERE {
    
      VALUES (?fragment) { <<fragments>> }
        
      ?unit a qudt:Unit .
      
      # FILTER EXISTS {
      #   ?unit ?up ?utext .
      #   FILTER (?up IN (qudt:symbol, rdfs:label))
      #   FILTER (
      #     LANG(?utext) = "" || LANGMATCHES(LANG(?utext), "en")
      #   )
      #   FILTER regex(str(?utext), ?fragment, "i")
      # }
      
      # This seems redundant to the above FILTER EXISTS part but allows to actually bind ?utext 
      OPTIONAL {
        ?unit ?up ?unit_text .
        FILTER (?up IN (qudt:symbol, rdfs:label))
        FILTER (
          LANG(?unit_text) = "" || LANGMATCHES(LANG(?unit_text), "en")
        )
        FILTER regex(str(?unit_text), ?fragment, "i")
      }
      
      FILTER (BOUND(?unit_text))
    
      OPTIONAL {
      
        ?unit qudt:hasQuantityKind ?kind .
        ?kind a qudt:QuantityKind .
        soqk:SI (qudt:hasBaseQuantityKind | qudt:systemDerivedQuantityKind) ?kind .

        # FILTER EXISTS {
        #   ?kind ?kp ?kind_text .
        #   FILTER (?kp IN (qudt:symbol, rdfs:label))
        #   FILTER (
        #       LANG(?kind_text) = "" || LANGMATCHES(LANG(?kind_text), "en")
        #   )
        #   FILTER regex(str(?kind_text), ?fragment, "i")
        # }
        
        OPTIONAL {
          ?kind ?kp ?kind_text .
          FILTER (?kp IN (qudt:symbol, rdfs:label))
          FILTER (
              LANG(?kind_text) = "" || LANGMATCHES(LANG(?kind_text), "en")
          )
          FILTER regex(str(?kind_text), ?fragment, "i")
        }
        
        FILTER (BOUND(?kind_text))
      }
    }
    """

    global lookup_generation_query
    lookup_generation_query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX soqk: <http://qudt.org/vocab/soqk/>
PREFIX sou: <http://qudt.org/vocab/sou/>
PREFIX qudt: <http://qudt.org/schema/qudt/>

SELECT ?unit ?symbol ?label_en ?label_en_us ?label_en_gb ?label_nolang ?kind ?kind_symbol ?kind_label_en ?kind_label_en_us ?kind_label_en_gb ?kind_label_nolang
WHERE {
    ?unit a qudt:Unit ;
    	qudt:symbol ?symbol ;
        qudt:applicableSystem sou:SI ;
    	qudt:hasQuantityKind ?kind .
    OPTIONAL {
        ?kind qudt:symbol ?kind_symbol.
    }
    
    OPTIONAL {
        ?kind rdfs:label ?kind_label_en .
        FILTER(LANG(?kind_label_en) = "en")
    }
    
    OPTIONAL {
        ?kind rdfs:label ?kind_label_en_gb .
        FILTER(LANG(?kind_label_en_gb) = "en-GB")
    }
    
    OPTIONAL {
        ?kind rdfs:label ?kind_label_en_us .
        FILTER(LANG(?kind_label_en_us) = "en-US")
    }
    
    OPTIONAL {
        ?kind rdfs:label ?kind_label_nolang .
        FILTER(LANG(?kind_label_nolang) = "")
    }
    
    OPTIONAL { 
        ?unit rdfs:label ?label_en . 
        FILTER(LANG(?label_en) = "en")
    }
    OPTIONAL { 
        ?unit rdfs:label ?label_en_us . 
        FILTER(LANG(?label_en_us) = "en-US")
    }
    OPTIONAL { 
        ?unit rdfs:label ?label_en_gb . 
        FILTER(LANG(?label_en_gb) = "en-GB")
    }
    OPTIONAL {
        ?unit rdfs:label ?label_nolang .
        FILTER( LANG(?label_nolang) = "" )
    }
}
"""

    global get_term_strings_query
    get_term_strings_query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX qudt: <http://qudt.org/schema/qudt/>

SELECT DISTINCT ?iri ?text
WHERE {
  VALUES ?iri { <<iris>> }

  # {
  #   # 1) The IRI string itself
  #   # it seems this does not work when querying in rdflib locally
  #   BIND(STR(?iri) AS ?text)
  # }
  # UNION
  {
    # 2) rdfs:label values
    ?iri rdfs:label ?text .
    FILTER (LANG(?text) = "" || LANGMATCHES(LANG(?text), "en"))
  }
  UNION
  {
    # 3) qudt:symbol values
    ?iri qudt:symbol ?text .
  }
}
    """

    global all_unit_query
    all_unit_query = """
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sou: <http://qudt.org/vocab/sou/>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT ?unit ?symbol ?abbreviation (COALESCE(?label_en_us, ?label_en_gb, ?label_en, ?label_nolang) AS ?descriptive_name) ?ucum_code ?has_quantity_kind ?iec61360code ?dbpedia_match ?wikidata_match
WHERE {
    ?unit a qudt:Unit ;
        # qudt:applicableSystem sou:SI ;
        qudt:symbol ?symbol .
        
    
    FILTER NOT EXISTS {
        ?unit dcterms:isReplacedBy ?otherUnit .
    }

            
    OPTIONAL { ?unit rdfs:label ?label_en . FILTER( LANG(?label_en) = "en" ) }
    OPTIONAL { ?unit rdfs:label ?label_en_us . FILTER( LANG(?label_en_us) = "en-US" ) }
    OPTIONAL { ?unit rdfs:label ?label_en_gb . FILTER( LANG(?label_en_gb) = "en-GB" ) }
    OPTIONAL { ?unit rdfs:label ?label_nolang . FILTER( LANG(?label_nolang) = "" ) }
    OPTIONAL { ?unit qudt:abbreviation ?abbreviation . }
    OPTIONAL { ?unit qudt:ucum_code ?ucum_code . }
    OPTIONAL { ?unit qudt:has_quantity_kind ?has_quantity_kind . }
    OPTIONAL { ?unit qudt:iec61360code ?iec61360code . }
    OPTIONAL { ?unit qudt:dbpediaMatch ?dbpedia_match . }
    OPTIONAL { ?unit qudt:wikidataMatch ?wikidata_match . }
}
"""

    # populate cache directly at startup - commented out for debugging because it adds 10s to server startup
    # get_all_units()


@functools.lru_cache(maxsize=None)
def search_unit_iri_by_symbol(symbol: str) -> str | None:
    result = unit_graph.query(coarse_unit_query.replace(
        "<<symbol_lister_list>>",
        f'("{symbol}")'
    ))

    if len(result) == 0:
        return None

    weighted_results = sorted([
        (unit_iri, unit_symbol, Levenshtein.distance(unit_symbol, symbol, weights=(3, 4, 1)))
        for unit_iri, unit_symbol in result
    ], key=lambda x: x[2])
    return weighted_results[0][0]


@functools.lru_cache(maxsize=None)
def search_unit_iri_by_name(name: str, limit=25) -> list[str]:
    result = unit_graph.query(unit_name_query.replace("<<name>>", f'("{name}")').replace("<<limit>>", str(limit)))
    if len(result) == 0:
        return []
    weighted_results = sorted([
        (unit_iri, Levenshtein.distance(unit_iri, name))
        for unit_iri, in result
    ], key=lambda x: x[1])
    sorted_iris = [str(x[0]) for x in weighted_results]
    return sorted_iris


@functools.lru_cache(maxsize=None)
def search_unit_iri_by_search_strings(search_strings: tuple[str, ...]) -> list[str]:
    replacement_string = ' '.join(f'("{fragment}")' for fragment in search_strings)
    result = unit_graph.query(simple_unit_query.replace("<<fragments>>", replacement_string))

    def simple_score(text: Literal) -> int:
        return min(Levenshtein.distance(text, fragment, weights=(3, 4, 1)) for fragment in search_strings)

    weighted_results = [
        (iri, text, simple_score(text))
        for iri, text in result
    ]

    weighted_results.sort(key=lambda x: x[2])
    iris = [str(iri) for (iri, text, weight) in weighted_results]  # remove duplicates but keep order

    return list(dict.fromkeys(iris))


# @functools.lru_cache(maxsize=None)
def fetch_unit_iri_by_fragments(fragments: tuple[str, ...]) -> list[str]:
    replacement_string = ' '.join(f'("{fragment}")' for fragment in fragments)
    # result = unit_graph.query(combined_query.replace("<<fragments>>", replacement_string))
    kind_result = unit_graph.query(quantity_kind_query.replace("<<fragments>>", replacement_string))
    kind_data = [tuple(match) for match in kind_result]
    unit_result = unit_graph.query(enhanced_unit_query.replace("<<fragments>>", replacement_string))
    unit_data = [tuple(match) for match in unit_result]

    _ = 42

    breakpoint_score = 50

    def simple_score(individual: URIRef, text: Literal) -> int:
        best_score = breakpoint_score
        for fragment in fragments:
            best_score = min(best_score, Levenshtein.distance(
                fragment,
                text.value,
                weights=(3, 4, 1)
            ))
        return best_score

    weighted_kinds = [
        (match, simple_score(match[0], match[1]))
        for match in kind_data
    ]
    kind_weight_lookup = collections.defaultdict(lambda: breakpoint_score)
    for match, weight in weighted_kinds:
        kind_weight_lookup[match[0]] = weight
    ordered_kinds = sorted(weighted_kinds, key=lambda x: x[1])

    weighted_units = [
        (match, simple_score(match[0], match[1]), kind_weight_lookup[match[2]])
        for match in unit_data
    ]

    prefiltered_units = [
        (match, unit_score, kind_score)
        for match, unit_score, kind_score in weighted_units
        if unit_score < breakpoint_score or kind_score < breakpoint_score
    ]

    sorted_units = sorted(prefiltered_units, key=lambda x: x[1] + x[2])

    return [str(x[0][0]) for x in sorted_units]
    _ = 42

    # if len(result) == 0:
    #     return []

    def calculate_score(unit: URIRef, unit_text: Literal, kind: URIRef | None, kind_text: Literal | None) -> int:
        best_kind_score = 100
        best_unit_score = 100
        for fragment in fragments:
            if kind is not None:
                best_kind_score = min(best_kind_score, Levenshtein.distance(
                    fragment,
                    kind_text.value,
                    weights=(3, 4, 1)
                ))
            best_unit_score = min(best_unit_score, Levenshtein.distance(
                fragment,
                unit_text.value,
                weights=(3, 4, 1)
            ))
        return best_unit_score

    weighted_results = [
        (match, calculate_score(*match))
        for match in result
    ]

    sorted_iris = [
        str(match[0])
        for match, _ in sorted(weighted_results, key=lambda x: x[1])
    ]

    return sorted_iris



@functools.lru_cache(maxsize=None)
def fetch_unit_object_from_qudt_unit_iri(unit_iris: tuple[str, ...]) -> list[UnitOfMeasure]:
    result_record = unit_graph.query(unit_details_query.replace(
        "<<unit_iri>>",
        ' '.join(f'(<{unit_iri}>)' for unit_iri in unit_iris)
    ))

    units = []

    for record in result_record:

        result_dict: dict[str, Any] = {
            key: str(value) if value else None
            for key, value in zip(record.labels, record)
        }

        exact_mapping_values = (
            {str(result_dict.pop('dbpedia_match'))} |
            {str(result_dict.pop('wikidata_match'))}
        ) - {'None'}
        result_dict['exact_mappings'] = [str(result_dict.pop('unit'))] + list(exact_mapping_values)

        units.append(UnitOfMeasure(**result_dict))
    return units


def normalize_comparison_string(text: str) -> str:
    return text.lower() \
        .replace("-", "_") \
        .replace(" ", "_")


@functools.lru_cache(maxsize=None)
def get_string_set_for_units(unit_iris: tuple[str, ...]) -> dict[str, str]:
    replacement_string = " ".join([f'<{iri}>' for iri in unit_iris])
    result = unit_graph.query(get_term_strings_query.replace("<<iris>>", replacement_string))
    return {
        normalize_comparison_string(str(text)): str(iri)
        for iri, text in result
    } | {
        # this here is needed as post-processing for rdflib since bind(str(?iri), ?text) does not work
        split_uri(iri)[1]: str(iri)
        for iri, _ in result
    }


# @functools.lru_cache(maxsize=None)
def find_best_matching_unit_for_text(unit_iris: tuple[str, ...], input_text: str) -> str | None:
    lookup = get_string_set_for_units(unit_iris)
    # best_weight = sys.maxsize
    normalized = normalize_comparison_string(input_text)
    best_ratio = 0.0
    selected_iri = None
    for text, iri in lookup.items():
        # weight = Levenshtein.distance(input_text, text, weights=(3, 4, 1))
        # if weight < best_weight:
        #     best_weight = weight
        #     selected_iri = iri
        ratio = Levenshtein.ratio(normalized, text)
        if ratio > best_ratio:
            best_ratio = ratio
            selected_iri = iri

    if best_ratio < 0.6:
        return None
    return selected_iri


def match_units_to_search_strings(unit_iris: tuple[str, ...], unit_texts: tuple[str, ...]) -> dict[str, UnitOfMeasure]:
    linkml_units = fetch_unit_object_from_qudt_unit_iri(unit_iris)
    linkml_unit_lookup = {
        unit.exact_mappings[0]: unit
        for unit in linkml_units
    }
    result = {
        text: linkml_unit_lookup.get(find_best_matching_unit_for_text(unit_iris, text), None)
        for text in unit_texts
    }
    return result


@functools.lru_cache(maxsize=None)
def get_all_units() -> list[UnitOfMeasure]:
    result_record = unit_graph.query(all_unit_query)
    units = []
    for record in result_record:

        result_dict: dict[str, Any] = {
            key: str(value) if value else None
            for key, value in zip(record.labels, record)
        }

        exact_mapping_values = (
            {str(result_dict.pop('dbpedia_match'))} |
            {str(result_dict.pop('wikidata_match'))}
        ) - {'None'}
        result_dict['exact_mappings'] = [str(result_dict.pop('unit'))] + list(exact_mapping_values)

        units.append(UnitOfMeasure(**result_dict))
    return units
