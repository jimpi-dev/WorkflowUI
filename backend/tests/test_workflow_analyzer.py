import pytest

from services.workflow_analyzer import (
    analyze_workflow,
    apply_default_inputs_to_graph,
    workflow_contains_workflow_ui_link,
)


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


def test_analyze_load_image_mask_image_and_channel_bindings():
    workflow = {
        "42": {
            "class_type": "LoadImageMask",
            "inputs": {"image": "mask.png", "channel": "alpha"},
        },
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    fields_by_key = {inp["key"]: inp for inp in result["inputs"]}
    binding_by_field = {b["field"]: b for b in result["bindings"]}
    assert "42.image" in keys
    assert "42.channel" in keys
    assert fields_by_key["42.image"]["type"] == "image"
    assert fields_by_key["42.channel"]["type"] == "select"
    assert fields_by_key["42.channel"]["options"] == ["alpha", "red", "green", "blue"]
    assert binding_by_field["image"]["key"] == "42.image"
    assert binding_by_field["channel"]["key"] == "42.channel"


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


def test_analyze_checkpoint_loader_produces_ckpt_name():
    workflow = {"1": {"class_type": "CheckpointLoader", "inputs": {"ckpt_name": "model.safetensors"}}}
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "1.ckpt_name" in keys
    inp = next(i for i in result["inputs"] if i["key"] == "1.ckpt_name")
    assert inp.get("optionSource") == "checkpoints"


def test_analyze_diffusion_model_loader_produces_unet_and_weight_dtype():
    workflow = {
        "2": {
            "class_type": "DiffusionModelLoader",
            "inputs": {"unet_name": "flux.safetensors", "weight_dtype": "fp16"},
        }
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "2.unet_name" in keys
    assert "2.weight_dtype" in keys


def test_analyze_load_diffusion_model_produces_same_inputs():
    workflow = {
        "3": {
            "class_type": "LoadDiffusionModel",
            "inputs": {"unet_name": "wan.safetensors", "weight_dtype": "default"},
        }
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "3.unet_name" in keys
    assert "3.weight_dtype" in keys


def test_analyze_stable_cascade_checkpoint_loader_produces_stage_inputs():
    workflow = {
        "4": {
            "class_type": "StableCascadeCheckpointLoader",
            "inputs": {"key_opt_b": "stage_b.safetensors", "key_opt_c": "stage_c.safetensors", "cache_mode": "all"},
        }
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "4.key_opt_b" in keys
    assert "4.key_opt_c" in keys
    assert "4.cache_mode" in keys
    b_inp = next(i for i in result["inputs"] if i["key"] == "4.key_opt_b")
    c_inp = next(i for i in result["inputs"] if i["key"] == "4.key_opt_c")
    assert b_inp.get("optionSource") == "stable_cascade_stage_b"
    assert c_inp.get("optionSource") == "stable_cascade_stage_c"


def test_analyze_stable_cascade_underscore_class_type():
    workflow = {
        "5": {
            "class_type": "StableCascade_CheckpointLoader",
            "inputs": {"key_opt_b": "b.safetensors", "key_opt_c": "c.safetensors", "cache_mode": "none"},
        }
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "5.key_opt_b" in keys
    assert "5.key_opt_c" in keys


def test_analyze_sd3_checkpoint_loader_produces_ckpt_name_and_shift():
    workflow = {
        "6": {"class_type": "SD3CheckpointLoader", "inputs": {"ckpt_name": "sd3_medium.safetensors", "shift": 3.0}}
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "6.ckpt_name" in keys
    assert "6.shift" in keys
    assert next(i for i in result["inputs"] if i["key"] == "6.shift")["default"] == 3.0


def test_analyze_sd3_load_checkpoint_alias():
    workflow = {"7": {"class_type": "SD3LoadCheckpoint", "inputs": {"ckpt_name": "sd3.safetensors", "shift": 6.0}}}
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "7.ckpt_name" in keys
    assert "7.shift" in keys


def test_analyze_flux_checkpoint_loader_produces_ckpt_name():
    workflow = {"8": {"class_type": "FluxCheckpointLoader", "inputs": {"ckpt_name": "flux1.safetensors"}}}
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "8.ckpt_name" in keys
    assert next(i for i in result["inputs"] if i["key"] == "8.ckpt_name").get("optionSource") == "checkpoints"


def test_analyze_stable_cascade_editor_format_widgets_values():
    workflow = {
        "nodes": [
            {
                "id": 9,
                "type": "StableCascadeCheckpointLoader",
                "widgets_values": ["stage_b.safetensors", "stage_c.safetensors", "all"],
            }
        ],
    }
    result = analyze_workflow(workflow)
    keys = {inp["key"] for inp in result["inputs"]}
    assert "9.key_opt_b" in keys
    assert "9.key_opt_c" in keys
    assert "9.cache_mode" in keys
    assert next(i for i in result["inputs"] if i["key"] == "9.key_opt_b")["default"] == "stage_b.safetensors"


def test_workflow_contains_workflow_ui_link():
    wf = {"5": {"class_type": "KSampler", "inputs": {}}, "10": {"class_type": "WorkflowUILink", "inputs": {}}}
    has_link, node_id = workflow_contains_workflow_ui_link(wf)
    assert has_link is True
    assert node_id == "10"


def test_workflow_contains_workflow_ui_link_none():
    wf = {"5": {"class_type": "KSampler", "inputs": {}}}
    has_link, node_id = workflow_contains_workflow_ui_link(wf)
    assert has_link is False
    assert node_id is None


def test_analyze_workflow_ui_link_schema():
    wf = {
        "10": {
            "class_type": "WorkflowUILink",
            "inputs": {
                "input_definitions": '[{"name": "prompt", "type": "text", "label": "Prompt"}, {"name": "steps", "type": "number", "label": "Steps"}]',
            },
        },
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 2
    keys = {i["key"] for i in result["inputs"]}
    assert "10.input_text_0" in keys
    assert "10.input_number_1" in keys
    assert any(i["label"] == "Prompt" for i in result["inputs"])
    assert any(i["label"] == "Steps" for i in result["inputs"])
    assert len(result["outputs"]) >= 1
    assert any(o.get("nodeId") == "7" and o.get("type") == "image" for o in result["outputs"])
    assert len(result["bindings"]) == 2


def test_analyze_workflow_ui_link_false_uses_regular_schema():
    wf = {
        "10": {"class_type": "WorkflowUILink", "inputs": {"input_definitions": "[]"}},
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=False)
    assert any(o.get("nodeId") == "7" and o.get("type") == "image" for o in result["outputs"])


def test_analyze_full_schema_includes_workflow_ui_link_inputs():
    """When use_workflow_ui_link=False, WorkflowUILink inputs still appear as entry points."""
    wf = {
        "10": {
            "class_type": "WorkflowUILink",
            "inputs": {
                "input_definitions": '[{"name": "prompt", "type": "text"}, {"name": "seed", "type": "seed"}]',
            },
        },
        "5": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 20}},
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=False)
    keys = {i["key"] for i in result["inputs"]}
    assert "10.input_text_0" in keys
    assert "10.input_number_1" in keys
    assert any(i["key"] == "10.input_text_0" and "prompt" in (i.get("label") or "").lower() for i in result["inputs"])


def test_analyze_workflow_ui_link_boolean():
    """WorkflowUILink supports boolean type in input_definitions."""
    wf = {
        "10": {
            "class_type": "WorkflowUILink",
            "inputs": {
                "input_definitions": '[{"name": "enable_upscale", "type": "boolean", "label": "Enable upscale"}]',
            },
        },
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 1
    inp = result["inputs"][0]
    assert inp["key"] == "10.input_boolean_0"
    assert inp["type"] == "boolean"
    assert inp["label"] == "Enable upscale"


def test_analyze_workflow_ui_link_input_definitions_label():
    """input_definitions JSON label is used when present; otherwise name is used."""
    wf = {
        "10": {
            "class_type": "WorkflowUILink",
            "inputs": {
                "input_definitions": '[{"name": "p", "type": "text", "label": "Prompt"}, {"name": "s", "type": "number", "label": "Steps"}]',
            },
        },
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 2
    inp0 = next(i for i in result["inputs"] if i["key"] == "10.input_text_0")
    inp1 = next(i for i in result["inputs"] if i["key"] == "10.input_number_1")
    assert inp0["label"] == "Prompt"
    assert inp1["label"] == "Steps"


def test_analyze_workflow_ui_link_editor_format_widgets_values():
    """WorkflowUILink with nodes array and widgets_values is correctly parsed (widget order: form_label, type_i, name_i)."""
    wf = {
        "nodes": [
            {
                "id": 10,
                "type": "WorkflowUILink",
                "widgets_values": [
                    "",
                    "text", "Positive prompt",
                    "number", "Steps",
                ],
                "pos": [0, 0],
                "size": {"0": 300, "1": 200},
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
            },
            {"id": 7, "type": "SaveImage", "inputs": [], "pos": [0, 0], "size": {"0": 200, "1": 100}, "flags": {}, "order": 0, "mode": 0, "properties": {}},
        ],
        "links": [],
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 2
    assert any(i["key"] == "10.input_text_0" and i["label"] == "Positive prompt" for i in result["inputs"])
    assert any(i["key"] == "10.input_number_1" and i["label"] == "Steps" for i in result["inputs"])


def test_analyze_nested_graph_unwrap():
    """Nested graph (e.g. workflow.graph) is unwrapped for analysis."""
    inner = {
        "nodes": [
            {"id": 10, "type": "WorkflowUILink", "widgets_values": ["", "text", "My field"], "pos": [0, 0], "size": {"0": 1, "1": 1}, "flags": {}, "order": 0, "mode": 0, "properties": {}},
            {"id": 7, "type": "SaveImage", "inputs": [], "pos": [0, 0], "size": {"0": 1, "1": 1}, "flags": {}, "order": 0, "mode": 0, "properties": {}},
        ],
        "links": [],
    }
    wf = {"workflow": {"graph": inner}}
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 1
    assert result["inputs"][0]["key"] == "10.input_text_0"
    assert result["inputs"][0]["label"] == "My field"


def test_analyze_workflow_ui_link_video_audio():
    """video and audio types map to input_video_N and input_audio_N."""
    wf = {
        "10": {
            "class_type": "WorkflowUILink",
            "inputs": {
                "input_definitions": '[{"name": "vid", "type": "video"}, {"name": "aud", "type": "audio"}]',
            },
        },
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    keys = {i["key"] for i in result["inputs"]}
    assert "10.input_video_0" in keys
    assert "10.input_audio_1" in keys
    typ0 = next(i["type"] for i in result["inputs"] if i["key"] == "10.input_video_0")
    typ1 = next(i["type"] for i in result["inputs"] if i["key"] == "10.input_audio_1")
    assert typ0 == "video"
    assert typ1 == "audio"


def test_workflow_contains_workflow_ui_link_display_name():
    """'WorkflowUI Link' (display name) is recognized like WorkflowUILink."""
    wf = {"5": {"class_type": "KSampler", "inputs": {}}, "10": {"class_type": "WorkflowUI Link", "inputs": {}}}
    has_link, node_id = workflow_contains_workflow_ui_link(wf)
    assert has_link is True
    assert node_id == "10"


def test_analyze_prompt_wrapped_api_format():
    """ComfyUI prompt-wrapped API format { prompt: { node_id: node } } is unwrapped."""
    wf = {
        "prompt": {
            "10": {
                "class_type": "WorkflowUILink",
                "inputs": {"input_definitions": '[{"name": "prompt", "type": "text"}]'},
            },
            "7": {"class_type": "SaveImage", "inputs": {}},
        },
        "client_id": "abc",
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 1
    assert result["inputs"][0]["key"] == "10.input_text_0"
    assert len(result["outputs"]) >= 1


def test_analyze_workflow_ui_link_input_definitions_fallback():
    """When input_definitions is missing but a JSON array exists in another key, fallback finds it."""
    wf = {
        "10": {
            "class_type": "WorkflowUILink",
            "inputs": {
                "form_label": '[{"name": "steps", "type": "number"}]',
            },
        },
        "7": {"class_type": "SaveImage", "inputs": {}},
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 1
    assert result["inputs"][0]["key"] == "10.input_number_0"


def test_analyze_workflow_ui_link_infer_from_outputs_when_definitions_empty():
    """When type widgets are empty, infer from connected outputs and names."""
    wf = {
        "nodes": [
            {
                "id": 79,
                "type": "WorkflowUILink",
                "widgets_values": ["", "", "Positive Prompt", "", "Random Seed", "", "Width(px)", "", "Height(Px)"],
                    "outputs": [
                        {"name": "text_0", "type": "STRING", "links": [1]},
                        {"name": "text_1", "type": "STRING", "links": None},
                        {"name": "number_1", "type": "INT", "links": [2]},
                    {"name": "number_2", "type": "INT", "links": [3]},
                    {"name": "number_3", "type": "INT", "links": [4]},
                ],
                "pos": [0, 0],
                "size": [300, 200],
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
            },
            {"id": 7, "type": "SaveImage", "inputs": [], "pos": [0, 0], "size": [200, 100], "flags": {}, "order": 0, "mode": 0, "properties": {}},
        ],
        "links": [],
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 4
    keys = {i["key"] for i in result["inputs"]}
    assert "79.input_text_0" in keys
    assert "79.input_number_1" in keys
    assert "79.input_number_2" in keys
    assert "79.input_number_3" in keys
    labels = {i["label"] for i in result["inputs"]}
    assert "Positive Prompt" in labels
    assert "Random Seed" in labels
    assert "Width(px)" in labels
    assert "Height(Px)" in labels
    seed_inp = next(i for i in result["inputs"] if i["key"] == "79.input_number_1")
    assert seed_inp["type"] == "seed"


def test_analyze_workflow_ui_link_infer_from_links_when_outputs_missing():
    """When outputs are missing/unexpected (ComfyUI-UE), infer from workflow links array."""
    wf = {
        "nodes": [
            {
                "id": 79,
                "type": "WorkflowUILink",
                    "widgets_values": ["", "", "Positive Prompt", "", "Random Seed", "", "Width(px)", "", "Height(Px)"],
                    "outputs": [],
                "pos": [0, 0],
                "size": [300, 200],
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
            },
            {"id": 9, "type": "SaveImage", "inputs": [], "pos": [0, 0], "size": [200, 100], "flags": {}, "order": 0, "mode": 0, "properties": {}},
        ],
        "links": [
            [73, 79, 0, "76", 0, "STRING"],
            [74, 79, 9, "75:73", 0, "INT"],
            [75, 79, 10, "75:68", 0, "INT"],
            [76, 79, 11, "75:69", 0, "INT"],
        ],
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 4
    keys = {i["key"] for i in result["inputs"]}
    assert "79.input_text_0" in keys
    assert "79.input_number_1" in keys
    assert "79.input_number_2" in keys
    assert "79.input_number_3" in keys
    labels = {i["label"] for i in result["inputs"]}
    assert "Positive Prompt" in labels
    assert "Random Seed" in labels
    assert "Width(px)" in labels
    assert "Height(Px)" in labels
    seed_inp = next(i for i in result["inputs"] if i["key"] == "79.input_number_1")
    assert seed_inp["type"] == "seed"


def test_analyze_workflow_ui_link_editor_format_display_name():
    """Full workflow export with type 'WorkflowUI Link' (display name) is recognized and parsed."""
    wf = {
        "version": 1,
        "nodes": [
            {
                "id": 10,
                    "type": "WorkflowUI Link",
                    "widgets_values": [
                        "",
                        "text", "Positive prompt",
                        "number", "Steps",
                    ],
                "pos": [0, 0],
                "size": {"0": 300, "1": 200},
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
            },
            {"id": 7, "type": "SaveImage", "inputs": [], "pos": [0, 0], "size": {"0": 200, "1": 100}, "flags": {}, "order": 0, "mode": 0, "properties": {}},
        ],
        "links": [],
    }
    result = analyze_workflow(wf, use_workflow_ui_link=True)
    assert len(result["inputs"]) == 2
    assert any(i["key"] == "10.input_text_0" and i["label"] == "Positive prompt" for i in result["inputs"])
    assert any(i["key"] == "10.input_number_1" and i["label"] == "Steps" for i in result["inputs"])


def test_apply_default_inputs_to_graph_image_filename():
    """Image inputs: default_inputs value can be string filename or {filename: name}; graph gets string."""
    workflow = {
        "1": {
            "class_type": "WorkflowUILink",
            "inputs": {"form_label": "Params", "input_image_0": ""},
        },
    }
    detected_inputs = [
        {"key": "1.input_image_0", "nodeId": "1", "field": "input_image_0", "label": "Image"},
    ]
    apply_default_inputs_to_graph(workflow, detected_inputs, {"1.input_image_0": "uploaded_xyz.png"})
    assert workflow["1"]["inputs"]["input_image_0"] == "uploaded_xyz.png"


def test_apply_default_inputs_to_graph_image_value_normalized_from_dict():
    """When default_inputs has {filename: 'name'}, apply_default_inputs_to_graph writes the string 'name'."""
    workflow = {
        "1": {
            "class_type": "WorkflowUILink",
            "inputs": {"form_label": "Params", "input_image_0": ""},
        },
    }
    detected_inputs = [
        {"key": "1.input_image_0", "nodeId": "1", "field": "input_image_0"},
    ]
    apply_default_inputs_to_graph(
        workflow, detected_inputs, {"1.input_image_0": {"filename": "hash123.jpg", "subfolder": ""}}
    )
    assert workflow["1"]["inputs"]["input_image_0"] == "hash123.jpg"


def test_apply_default_inputs_to_graph_multiple_image_slots():
    """Multiple image slots can receive different filenames; same filename can be reused for multiple slots."""
    workflow = {
        "1": {
            "class_type": "WorkflowUILink",
            "inputs": {"form_label": "Params", "input_image_0": "", "input_image_1": ""},
        },
    }
    detected_inputs = [
        {"key": "1.input_image_0", "nodeId": "1", "field": "input_image_0"},
        {"key": "1.input_image_1", "nodeId": "1", "field": "input_image_1"},
    ]
    default_inputs = {
        "1.input_image_0": "upload_a.png",
        "1.input_image_1": "upload_a.png",
    }
    apply_default_inputs_to_graph(workflow, detected_inputs, default_inputs)
    assert workflow["1"]["inputs"]["input_image_0"] == "upload_a.png"
    assert workflow["1"]["inputs"]["input_image_1"] == "upload_a.png"
