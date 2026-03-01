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
