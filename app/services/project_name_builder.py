from app.repositories.reference_object_repository import ReferenceObjectRepository


def load_project_reference_maps(reference_repo: ReferenceObjectRepository, level_ids: list[str]):
    levels_by_id = reference_repo.get_levels_tree(level_ids)
    object_ids = [level.object_id for level in levels_by_id.values() if level.object_id]
    objects = reference_repo.get_objects_by_ids(object_ids)
    objects_by_id = {obj.id: obj for obj in objects}

    contract_ids = [level.contract_id for level in levels_by_id.values() if level.contract_id]
    contracts = reference_repo.get_contracts_by_ids(contract_ids)
    contracts_by_id = {contract.id: contract for contract in contracts}

    work_type_ids = [level.work_type for level in levels_by_id.values() if level.work_type]
    work_types = reference_repo.get_work_types_by_ids(work_type_ids)
    work_types_by_id = {work_type.id: work_type for work_type in work_types}

    return levels_by_id, objects_by_id, contracts_by_id, work_types_by_id


def build_project_name(
    object_level_id,
    levels_by_id,
    objects_by_id,
    contracts_by_id,
    work_types_by_id,
):
    if not object_level_id:
        return None

    level = levels_by_id.get(object_level_id)
    if not level:
        return None

    parts_by_type = {"section": None, "agreement": None, "worktype": None}
    current = level
    while current:
        if current.level_type == "section":
            parts_by_type["section"] = current.name or parts_by_type["section"]
        elif current.level_type == "agreement":
            contract_name = None
            if current.contract_id and contracts_by_id.get(current.contract_id):
                contract_name = contracts_by_id[current.contract_id].name
            parts_by_type["agreement"] = contract_name or current.name or parts_by_type["agreement"]
        elif current.level_type == "worktype":
            work_type_name = None
            if current.work_type and work_types_by_id.get(current.work_type):
                work_type_name = work_types_by_id[current.work_type].name
            parts_by_type["worktype"] = work_type_name or current.name or parts_by_type["worktype"]

        if not current.parent_id:
            break
        current = levels_by_id.get(current.parent_id)

    obj = objects_by_id.get(level.object_id)
    object_name = None
    if obj:
        object_name = obj.short_name or obj.full_name

    name_parts = [
        object_name,
        parts_by_type["section"],
        parts_by_type["agreement"],
        parts_by_type["worktype"],
    ]
    filtered = [part for part in name_parts if part]
    return " - ".join(filtered) if filtered else None
