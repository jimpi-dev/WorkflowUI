import pytest

from routers.execution import apply_binding, resolve_node
from services.run_executor import (
    MAX_SEED,
    _normalize_workflow_ui_link_inputs,
    _resolve_seed,
    prompt_to_api_format,
)


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


def test_prompt_to_api_format_resolves_links_saveimage():
    """ComfyUI 0.4 format: nodes have inputs array with link id; links array maps to [origin_id, origin_slot]."""
    workflow = {
        "nodes": [
            {
                "id": 93,
                "type": "WorkflowUILink",
                "inputs": [],
                "widgets_values": ["Params", "image", "Input", "", ""],
                "outputs": [{"name": "image_0", "type": "IMAGE", "links": [1], "slot_index": 0}],
                "pos": [0, 0],
                "size": {"0": 300, "1": 200},
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
            },
            {
                "id": 94,
                "type": "SaveImage",
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": 1},
                    {"name": "filename_prefix", "type": "STRING", "link": None},
                ],
                "widgets_values": ["ComfyUI"],
                "pos": [0, 0],
                "size": {"0": 200, "1": 100},
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
            },
        ],
        "links": [
            [1, "93", 0, "94", 0, "IMAGE"],
        ],
    }
    out = prompt_to_api_format(workflow)
    assert "94" in out
    assert out["94"]["class_type"] == "SaveImage"
    assert out["94"]["inputs"].get("images") == ["93", 0]
    assert out["94"]["inputs"].get("filename_prefix") == "ComfyUI"


def test_prompt_to_api_format_only_includes_output_reachable_nodes():
    """Only nodes reachable backward from output nodes (SaveImage, etc.) are included."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "widgets_values": ["test.png"], "mode": 0},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "type": "IMAGE", "link": 10}], "widgets_values": ["Out"], "mode": 0},
            {"id": 99, "type": "KSampler", "widgets_values": [0, 20, 7, "euler", "normal", 1.0], "mode": 0},
        ],
        "links": [[10, "1", 0, "2", 0, "IMAGE"]],
    }
    out = prompt_to_api_format(workflow)
    assert "1" in out
    assert "2" in out
    assert "99" not in out


def test_prompt_to_api_format_excludes_disabled_output_branch():
    """When all output nodes are disabled we don't filter; only mode-4 nodes are skipped."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "widgets_values": ["a.png"], "mode": 0},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "type": "IMAGE", "link": 10}], "widgets_values": ["Out"], "mode": 4},
        ],
        "links": [[10, "1", 0, "2", 0, "IMAGE"]],
    }
    out = prompt_to_api_format(workflow)
    assert "1" in out
    assert "2" not in out


def test_prompt_to_api_format_object_style_links():
    """Links as objects { id, origin_id, target_id, ... } are supported (ComfyUI schema)."""
    workflow = {
        "nodes": [
            {"id": 10, "type": "LoadImage", "widgets_values": ["x.png"], "mode": 0},
            {"id": 20, "type": "SaveImage", "inputs": [{"name": "images", "type": "IMAGE", "link": 99}], "widgets_values": ["Out"], "mode": 0},
        ],
        "links": [
            {"id": 99, "origin_id": 10, "origin_slot": 0, "target_id": 20, "target_slot": 0, "type": "IMAGE"},
        ],
    }
    out = prompt_to_api_format(workflow)
    assert "10" in out
    assert "20" in out
    assert out["20"]["inputs"].get("images") == ["10", 0]


def test_prompt_to_api_format_multiple_hops_from_output():
    """Backward traversal includes all nodes in the chain (A -> B -> SaveImage)."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "widgets_values": ["a.png"], "mode": 0},
            {"id": 2, "type": "SomeFilter", "inputs": [{"name": "image", "type": "IMAGE", "link": 10}], "widgets_values": [], "mode": 0},
            {"id": 3, "type": "SaveImage", "inputs": [{"name": "images", "type": "IMAGE", "link": 11}], "widgets_values": ["Out"], "mode": 0},
        ],
        "links": [
            [10, "1", 0, "2", 0, "IMAGE"],
            [11, "2", 0, "3", 0, "IMAGE"],
        ],
    }
    out = prompt_to_api_format(workflow)
    assert set(out.keys()) == {"1", "2", "3"}
    assert out["3"]["inputs"].get("images") == ["2", 0]
    assert out["2"]["inputs"].get("image") == ["1", 0]


def test_prompt_to_api_format_only_required_nodes_no_dangling_refs():
    """Every input [node_id, slot] in the final prompt refers to a node in the prompt."""
    from services.run_executor import _ensure_only_referenced_nodes_in_prompt
    prompt = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "a.png"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "Out"}},
        "3": {"class_type": "KSampler", "inputs": {"model": ["99", 0]}},
    }
    _ensure_only_referenced_nodes_in_prompt(prompt)
    assert "1" in prompt
    assert "2" in prompt
    assert "3" in prompt
    assert prompt["2"]["inputs"]["images"] == ["1", 0]
    assert "model" not in prompt["3"]["inputs"]


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


def test_apply_binding_workflow_ui_link_image_sets_filename():
    """WorkflowUILink image slots accept a string filename (ComfyUI input dir); value is passed through."""
    node = {
        "class_type": "WorkflowUILink",
        "inputs": {"form_label": "Params", "input_image_0": ""},
    }
    apply_binding(node, "input_image_0", "a1b2c3d4e5f6.png")
    assert node["inputs"]["input_image_0"] == "a1b2c3d4e5f6.png"


def test_normalize_workflow_ui_link_preserves_image_filename():
    """_normalize_workflow_ui_link_inputs keeps string image filenames; only coerces empty/invalid to ''."""
    prompt = {
        "1": {
            "class_type": "WorkflowUILink",
            "inputs": {"input_image_0": "uploaded_abc123.jpg", "input_image_1": ""},
        },
    }
    _normalize_workflow_ui_link_inputs(prompt)
    assert prompt["1"]["inputs"]["input_image_0"] == "uploaded_abc123.jpg"
    assert prompt["1"]["inputs"]["input_image_1"] == ""


def test_normalize_workflow_ui_link_invalid_image_value_becomes_empty():
    """Non-string or invalid image values are coerced to '' so the node does not crash."""
    prompt = {
        "1": {
            "class_type": "WorkflowUILink",
            "inputs": {"input_image_0": None, "input_image_1": 123, "input_image_2": "valid.png"},
        },
    }
    _normalize_workflow_ui_link_inputs(prompt)
    assert prompt["1"]["inputs"]["input_image_0"] == ""
    assert prompt["1"]["inputs"]["input_image_1"] == ""
    assert prompt["1"]["inputs"]["input_image_2"] == "valid.png"


def test_apply_binding_multiple_image_slots():
    """WorkflowUILink can have multiple image slots; each gets its own filename."""
    node = {
        "class_type": "WorkflowUILink",
        "inputs": {"form_label": "Params", "input_image_0": "", "input_image_1": ""},
    }
    apply_binding(node, "input_image_0", "first_abc.png")
    apply_binding(node, "input_image_1", "second_def.jpg")
    assert node["inputs"]["input_image_0"] == "first_abc.png"
    assert node["inputs"]["input_image_1"] == "second_def.jpg"
