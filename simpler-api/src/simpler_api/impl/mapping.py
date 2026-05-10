from linkml_runtime.linkml_model.units import UnitOfMeasure

from simpler_model import Unit


def make_unit(linkml_unit: UnitOfMeasure | None) -> Unit | None:
    if linkml_unit is None:
        return None
    return Unit(
        id=linkml_unit.exact_mappings[0],
        symbol=linkml_unit.symbol,
        description=linkml_unit.descriptive_name
    )

