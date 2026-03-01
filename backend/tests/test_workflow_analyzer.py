import pytest

from services.workflow_analyzer import analyze_workflow


def test_analyze_returns_inputs_outputs_bindings(sample_workflow_graph):
    result = analyze_workflow(sample_workflow_graph)
    assert "inputs" in result
    assert "outputs" in result
    assert "bindings" in result
    assert isinstance(result["inputs"], list)
    assert isinstance(result["outputs"], list)
    assert isinstance(result["bindings"], list)


def test_analyze_ksampler_inputs(sample_workflow_graph):
    result = analyze_workflow(sample_workflow_graph)
    keys = {inp["key"] for inp in result["inputs"]}
    assert any("3.seed" in k for k in keys) or "3.seed" in keys
    assert any("3.steps" in k for k in keys) or "3.steps" in keys


def test_analyze_save_image_output():
    workflow = {"7": {"class_type": "SaveImage", "inputs": {}}}
    result = analyze_workflow(workflow)
    assert len(result["outputs"]) >= 1
    assert any(o.get("type") == "image" for o in result["outputs"])


def test_analyze_save_image_output_only_not_input():
    workflow = {"7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ComfyUI"}}}
    result = analyze_workflow(workflow)
    assert any(o.get("nodeId") == "7" and o.get("type") == "image" for o in result["outputs"])
    input_keys = {inp["key"] for inp in result["inputs"]}
    assert not any(k.startswith("7.") for k in input_keys)


def test_analyze_vhs_video_combine_output():
    workflow = {"129": {"class_type": "VHS_VideoCombine", "inputs": {}}}
    result = analyze_workflow(workflow)
    assert len(result["outputs"]) >= 1
    assert any(o.get("type") == "video" for o in result["outputs"])


def test_analyze_empty_workflow():
    result = analyze_workflow({})
    assert result["inputs"] == []
    assert result["outputs"] == []
    assert result["bindings"] == []
    assert "internal_nodes" not in result or result.get("internal_nodes") == []


def test_analyze_vaedecode_internal_node_no_output():
    workflow = {"17": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["12", 2]}, "_meta": {"title": "VAE Decode"}}}
    result = analyze_workflow(workflow)
    assert result["outputs"] == []
    assert "internal_nodes" in result
    assert len(result["internal_nodes"]) == 1
    assert result["internal_nodes"][0]["classType"] == "VAEDecode"
    assert result["internal_nodes"][0]["label"] == "VAE Decode"


def test_analyze_unknown_node_skipped():
    workflow = {"99": {"class_type": "UnknownNode", "inputs": {}}}
    result = analyze_workflow(workflow)
    assert "inputs" in result
    assert "bindings" in result


def test_analyze_empty_latent_image_produces_width_height_bindings():
    workflow = {
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    binding_keys = {b["key"] for b in result["bindings"]}
    assert "5.width" in keys
    assert "5.height" in keys
    assert "5.batch_size" in keys
    assert "5.width" in binding_keys
    assert "5.height" in binding_keys
    assert "5.batch_size" in binding_keys
    for b in result["bindings"]:
        if b["key"] == "5.width":
            assert b["nodeId"] == "5"
            assert b["field"] == "width"
        elif b["key"] == "5.height":
            assert b["nodeId"] == "5"
            assert b["field"] == "height"


def test_analyze_editor_format_empty_latent_produces_dimension_bindings():
    workflow = {
        "version": 1,
        "nodes": [
            {
                "id": 5,
                "type": "EmptyLatentImage",
                "widgets_values": [512, 512, 1],
            }
        ],
        "links": [],
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    binding_keys = {b["key"] for b in result["bindings"]}
    assert "5.width" in keys
    assert "5.height" in keys
    assert "5.width" in binding_keys
    assert "5.height" in binding_keys


def test_analyze_sdxl_latent_picker_produces_override_bindings():
    workflow = {
        "nodes": [
            {
                "id": 18,
                "type": "SDXLEmptyLatentSizePicker+",
                "widgets_values": ["1024x1024 (1.0)", 1, 1152, 896],
            }
        ],
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    binding_keys = {b["key"] for b in result["bindings"]}
    assert "18.width_override" in keys
    assert "18.height_override" in keys
    assert "18.width_override" in binding_keys
    assert "18.height_override" in binding_keys


def test_analyze_lora_loader_produces_lora_name_and_strengths():
    workflow = {
        "10": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "foo.safetensors", "strength_model": 0.8, "strength_clip": 1.0},
            "_meta": {"title": "LoRA"},
        }
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "10.lora_name" in keys
    assert "10.strength_model" in keys
    assert "10.strength_clip" in keys


def test_analyze_lycoris_loader_node_produces_lycoris_type():
    workflow = {
        "20": {
            "class_type": "LycorisLoaderNode",
            "inputs": {
                "lora_name": "bar.safetensors",
                "strength_model": 1.0,
                "strength_clip": 0.5,
                "lycoris_type": "LoHA",
            },
            "_meta": {"title": "LyCORIS"},
        }
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "20.lora_name" in keys
    assert "20.lycoris_type" in keys
