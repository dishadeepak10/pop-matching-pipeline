import json


def load_pop(case_number, output_dir):

    json_path = (
        output_dir
        / f"{case_number}_POP_Document"
        / "extracted.json"
    )

    if not json_path.exists():
        return None

    with open(
        json_path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    fields = data.get("fields", [])

    pop_data = {}

    for field in fields:

        field_name = field.get("field_name")
        value = field.get("value")

        if field_name and value not in (None, ""):
            pop_data[field_name] = value

    return pop_data