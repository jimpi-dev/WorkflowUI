import pytest

from routers.execution import apply_binding, resolve_node
from services.run_executor import prompt_to_api_format, _resolve_seed, MAX_SEED


def test_apply_binding_sets_latent_width_height():
    node = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    }
    apply_binding(node, "width", 1024)
    apply_binding(node, "height", 768)
    assert node["inputs"]["width"] == 1024
    assert node["inputs"]["height"] == 768
    assert node["inputs"]["batch_size"] == 1


def test_apply_binding_coerces_string_to_int():
    node = {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}}
    apply_binding(node, "width", "1024")
    apply_binding(node, "height", 768)
    assert node["inputs"]["width"] == 1024
    assert node["inputs"]["height"] == 768
    assert isinstance(node["inputs"]["width"], int)
    assert isinstance(node["inputs"]["height"], int)


def test_apply_binding_creates_inputs_dict_if_missing():
    node = {"class_type": "EmptyLatentImage"}
    apply_binding(node, "width", 800)
    assert "inputs" in node
    assert node["inputs"]["width"] == 800


def test_apply_binding_sdxl_empty_latent_size_picker():
    node = {
        "class_type": "SDXLEmptyLatentSizePicker+",
        "inputs": {"width_override": 1024, "height_override": 1024, "batch_size": 1},
    }
    apply_binding(node, "width_override", 1152)
    apply_binding(node, "height_override", 896)
    assert node["inputs"]["width_override"] == 1152
    assert node["inputs"]["height_override"] == 896
    assert isinstance(node["inputs"]["width_override"], int)
    assert isinstance(node["inputs"]["height_override"], int)


def test_apply_binding_lora_nested():
    node = {
        "class_type": "Power Lora Loader (rgthree)",
        "inputs": {
            "lora_5": {"on": False, "lora": "OldLora.safetensors", "strength": 0.8},
        },
    }
    apply_binding(node, "lora_5.lora", "NewLora.safetensors")
    apply_binding(node, "lora_5.strength", 0.85)
    apply_binding(node, "lora_5.on", True)
    assert node["inputs"]["lora_5"]["lora"] == "NewLora.safetensors"
    assert node["inputs"]["lora_5"]["strength"] == 0.85
    assert node["inputs"]["lora_5"]["on"] is True


def test_resolve_node_finds_top_level_node():
    prompt = {
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
        "7": {"class_type": "KSampler", "inputs": {"seed": 0}},
    }
    n = resolve_node(prompt, "5")
    assert n is not None
    assert n["class_type"] == "EmptyLatentImage"
    n7 = resolve_node(prompt, "7")
    assert n7 is not None
    assert n7["class_type"] == "KSampler"


def test_resolve_node_accepts_string_id():
    prompt = {"5": {"class_type": "EmptyLatentImage", "inputs": {}}}
    assert resolve_node(prompt, "5") is not None


def test_full_binding_flow_patches_latent_node():
    prompt = {
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    }
    values = {"5.width": 1152, "5.height": 896, "5.batch_size": 2}
    bindings = [
        {"key": "5.width", "nodeId": "5", "field": "width"},
        {"key": "5.height", "nodeId": "5", "field": "height"},
        {"key": "5.batch_size", "nodeId": "5", "field": "batch_size"},
    ]
    for b in bindings:
        key = b["key"]
        node_id = str(b["nodeId"])
        field_path = b["field"]
        if key not in values:
            continue
        value = values[key]
        node = resolve_node(prompt, node_id)
        assert node is not None
        apply_binding(node, field_path, value)
    assert prompt["5"]["inputs"]["width"] == 1152
    assert prompt["5"]["inputs"]["height"] == 896
    assert prompt["5"]["inputs"]["batch_size"] == 2


def test_prompt_to_api_format_converts_editor_format():
    editor = {
        "version": 1,
        "nodes": [
            {"id": 5, "type": "EmptyLatentImage", "widgets_values": [1024, 768, 2]},
        ],
        "links": [],
    }
    api = prompt_to_api_format(editor)
    assert "5" in api
    assert api["5"]["class_type"] == "EmptyLatentImage"
    assert api["5"]["inputs"]["width"] == 1024
    assert api["5"]["inputs"]["height"] == 768
    assert api["5"]["inputs"]["batch_size"] == 2


def test_prompt_to_api_format_sdxl_latent_picker_editor():
    editor = {
        "nodes": [
            {"id": 12, "type": "SDXLEmptyLatentSizePicker+", "widgets_values": ["1024x1024 (1.0)", 2, 1152, 896]},
        ],
    }
    api = prompt_to_api_format(editor)
    assert "12" in api
    assert api["12"]["class_type"] == "SDXLEmptyLatentSizePicker+"
    assert api["12"]["inputs"]["resolution"] == "1024x1024 (1.0)"
    assert api["12"]["inputs"]["batch_size"] == 2
    assert api["12"]["inputs"]["width_override"] == 1152
    assert api["12"]["inputs"]["height_override"] == 896


def test_prompt_to_api_format_passthrough_flat_format():
    flat = {"5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}}}
    out = prompt_to_api_format(flat)
    assert out is flat
    assert out["5"]["inputs"]["width"] == 512


def test_resolve_seed_zero_generates_random_in_range():
    for _ in range(20):
        s = _resolve_seed(0)
        assert 0 <= s <= MAX_SEED


def test_resolve_seed_clamped_to_max():
    assert _resolve_seed(MAX_SEED + 1) == MAX_SEED
    assert _resolve_seed(2**63 - 1) == MAX_SEED
    assert _resolve_seed(10 * MAX_SEED) == MAX_SEED


def test_resolve_seed_preserves_valid_seed():
    assert _resolve_seed(1) == 1
    assert _resolve_seed(12345) == 12345
    assert _resolve_seed(MAX_SEED) == MAX_SEED


def test_resolve_seed_empty_or_none_treated_as_zero():
    for raw in (None, ""):
        s = _resolve_seed(raw)
        assert 0 <= s <= MAX_SEED
