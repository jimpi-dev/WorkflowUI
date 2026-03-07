import re
from typing import Any

WORKFLOW_UI_LINK_CLASS = "WorkflowUILink"

def _workflow_ui_link_widget_order() -> list[str]:
    order = ["form_label"]
    for i in range(8):
        order.append(f"type_{i}")
        order.append(f"name_{i}")
    for i in range(8):
        order.append(f"input_text_{i}")
    for i in range(8):
        order.append(f"input_number_{i}")
    for i in range(8):
        order.append(f"input_image_{i}")
    for i in range(8):
        order.append(f"input_video_{i}")
    for i in range(8):
        order.append(f"input_audio_{i}")
    for i in range(8):
        order.append(f"input_boolean_{i}")
    return order


_WIDGET_ORDER: dict[str, list[str]] = {
    WORKFLOW_UI_LINK_CLASS: _workflow_ui_link_widget_order(),
    "WorkflowUI Link": _workflow_ui_link_widget_order(),
    "EmptyLatentImage": ["width", "height", "batch_size"],
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "SDXLEmptyLatentSizePicker+": ["resolution", "batch_size", "width_override", "height_override"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "DiffusionModelLoader": ["unet_name", "weight_dtype"],
    "LoadDiffusionModel": ["unet_name", "weight_dtype"],
    "StableCascadeCheckpointLoader": ["key_opt_b", "key_opt_c", "cache_mode"],
    "StableCascade_CheckpointLoader": ["key_opt_b", "key_opt_c", "cache_mode"],
    "SD3CheckpointLoader": ["ckpt_name", "shift"],
    "SD3LoadCheckpoint": ["ckpt_name", "shift"],
}


def _is_api_format_graph(d: dict[str, Any]) -> bool:
    """True if d looks like ComfyUI API format: { node_id: { class_type, inputs } }."""
    if not d or not isinstance(d, dict):
        return False
    for v in d.values():
        if isinstance(v, dict) and ("class_type" in v or "inputs" in v):
            return True
    return False


def _extract_workflow_for_analysis(workflow: dict[str, Any]) -> dict[str, Any]:
    """Unwrap nested structures (e.g. { workflow: { graph: {...} } }, { prompt: {...} }) so we get the analyzable graph."""
    if not isinstance(workflow, dict):
        return workflow
    if workflow.get("nodes") is not None:
        return workflow
    if _is_api_format_graph(workflow):
        return workflow
    for key in ("graph", "workflow", "prompt"):
        inner = workflow.get(key)
        if isinstance(inner, dict) and inner.get("nodes") is not None:
            return inner
        if isinstance(inner, dict) and _is_api_format_graph(inner):
            return inner
        if isinstance(inner, dict):
            deeper = inner.get("graph") or inner.get("workflow")
            if isinstance(deeper, dict) and deeper.get("nodes") is not None:
                return deeper
            if isinstance(deeper, dict) and _is_api_format_graph(deeper):
                return deeper
    return workflow


def _normalize_to_api_format(workflow: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(workflow, dict):
        return workflow
    workflow = _extract_workflow_for_analysis(workflow)
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        return workflow
    out: dict[str, Any] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        if nid is None:
            continue
        node_id = str(nid)
        class_type = node.get("type") or node.get("class_type")
        if not class_type:
            continue
        if class_type == "WorkflowUI Link":
            class_type = WORKFLOW_UI_LINK_CLASS
        inputs: dict[str, Any] = {}
        widgets_values = node.get("widgets_values") or node.get("widgetsValues") or node.get("widget_values")
        if isinstance(widgets_values, dict):
            inputs = dict(widgets_values)
        elif isinstance(widgets_values, list):
            widget_order = _WIDGET_ORDER.get(class_type)
            if not widget_order:
                spec = NODE_SPECS.get(class_type)
                if isinstance(spec, dict) and isinstance(spec.get("fixedInputs"), dict):
                    widget_order = list(spec["fixedInputs"].keys())
            if widget_order:
                for idx, field in enumerate(widget_order):
                    if idx < len(widgets_values):
                        inputs[field] = widgets_values[idx]
        if not inputs and isinstance(node.get("inputs"), dict):
            inputs = dict(node["inputs"])
        meta = node.get("_meta")
        if not meta and isinstance(node.get("properties"), dict):
            s_r_name = (node.get("properties") or {}).get("Node name for S&R")
            if isinstance(s_r_name, str) and s_r_name.strip():
                meta = {"title": s_r_name.strip()}
        normalized = {"class_type": class_type, "inputs": inputs}
        if meta:
            normalized["_meta"] = meta
        if class_type == WORKFLOW_UI_LINK_CLASS:
            raw_outputs = node.get("outputs")
            if isinstance(raw_outputs, list):
                normalized["_raw_outputs"] = raw_outputs
        out[node_id] = normalized
    return out if out else workflow


def apply_default_inputs_to_graph(
    workflow: dict[str, Any],
    detected_inputs: list[dict[str, Any]],
    default_inputs: dict[str, Any],
) -> None:
    if not default_inputs or not isinstance(default_inputs, dict):
        return
    key_to_binding: dict[str, tuple[str, str]] = {}
    for inp in detected_inputs or []:
        if not isinstance(inp, dict):
            continue
        k = inp.get("key")
        nid = inp.get("nodeId")
        field = inp.get("field")
        if k is not None and nid is not None and field is not None:
            key_to_binding[str(k)] = (str(nid), str(field))
    for key, value in default_inputs.items():
        binding = key_to_binding.get(key)
        if not binding:
            continue
        node_id, field = binding
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        if isinstance(value, dict) and "filename" in value:
            value = value["filename"]
        inputs[field] = value


def _layout_map(rows: list[list[str]]) -> dict[str, dict[str, int]]:
    out = {}
    for row_idx, row in enumerate(rows):
        for col_idx, field in enumerate(row):
            out[field] = {"row": row_idx, "col": col_idx}
    return out


LORA_GROUP_MATCH = re.compile(r"^lora_\d+$")
OUTPUT_ONLY_NODE_TYPES = {"SaveImage", "Save Image", "Save Image (api)", "SaveImageNode"}

NODE_SPECS: dict[str, dict[str, Any]] = {
    "KSampler": {
        "fixedInputs": {
            "seed": {"type": "seed", "label": "Seed"},
            "steps": {"type": "number", "label": "Steps", "min": 1, "max": 150, "slider": True},
            "cfg": {"type": "number", "label": "CFG Scale", "min": 1, "max": 20, "slider": True},
            "sampler_name": {"type": "select", "label": "Sampler", "optionSource": "samplers"},
        }
    },
    "CLIPTextEncode": {
        "fixedInputs": {
            "text": {"type": "text", "label": "Prompt"},
        }
    },
    "LoadImage": {
        "fixedInputs": {
            "image": {"type": "image", "label": "Image"},
        }
    },
    "CheckpointLoaderSimple": {
        "fixedInputs": {
            "ckpt_name": {"type": "select", "label": "Checkpoint", "optionSource": "checkpoints"},
        }
    },
    "CheckpointLoader": {
        "fixedInputs": {
            "ckpt_name": {"type": "select", "label": "Checkpoint", "optionSource": "checkpoints"},
        }
    },
    "DiffusionModelLoader": {
        "fixedInputs": {
            "unet_name": {"type": "select", "label": "Diffusion model", "optionSource": "checkpoints"},
            "weight_dtype": {"type": "select", "label": "Weight dtype", "options": ["default", "fp8", "fp16", "bf16"]},
        }
    },
    "LoadDiffusionModel": {
        "fixedInputs": {
            "unet_name": {"type": "select", "label": "Diffusion model", "optionSource": "checkpoints"},
            "weight_dtype": {"type": "select", "label": "Weight dtype", "options": ["default", "fp8", "fp16", "bf16"]},
        }
    },
    "StableCascadeCheckpointLoader": {
        "fixedInputs": {
            "key_opt_b": {"type": "select", "label": "Stage B model", "optionSource": "stable_cascade_stage_b"},
            "key_opt_c": {"type": "select", "label": "Stage C model", "optionSource": "stable_cascade_stage_c"},
            "cache_mode": {"type": "select", "label": "Cache mode", "options": ["none", "stage_b", "stage_c", "all"]},
        }
    },
    "StableCascade_CheckpointLoader": {
        "fixedInputs": {
            "key_opt_b": {"type": "select", "label": "Stage B model", "optionSource": "stable_cascade_stage_b"},
            "key_opt_c": {"type": "select", "label": "Stage C model", "optionSource": "stable_cascade_stage_c"},
            "cache_mode": {"type": "select", "label": "Cache mode", "options": ["none", "stage_b", "stage_c", "all"]},
        }
    },
    "SD3CheckpointLoader": {
        "fixedInputs": {
            "ckpt_name": {"type": "select", "label": "Checkpoint", "optionSource": "checkpoints"},
            "shift": {"type": "number", "label": "Shift", "min": 0, "max": 10, "step": 0.1, "slider": True},
        }
    },
    "SD3LoadCheckpoint": {
        "fixedInputs": {
            "ckpt_name": {"type": "select", "label": "Checkpoint", "optionSource": "checkpoints"},
            "shift": {"type": "number", "label": "Shift", "min": 0, "max": 10, "step": 0.1, "slider": True},
        }
    },
    "FluxCheckpointLoader": {
        "fixedInputs": {
            "ckpt_name": {"type": "select", "label": "Checkpoint", "optionSource": "checkpoints"},
        }
    },
    "ImageScaleBy": {
        "fixedInputs": {
            "scale_by": {"type": "number", "label": "Scale by", "min": 0.01, "max": 4, "step": 0.01, "slider": True},
        },
    },
    "SaveImage": {
        "fixedInputs": {
            "filename_prefix": {"type": "text", "label": "Filename prefix"},
        },
        "outputs": {"type": "image"},
    },
    "Save Image": {"fixedInputs": {"filename_prefix": {"type": "text", "label": "Filename prefix"}}, "outputs": {"type": "image"}},
    "Save Image (api)": {"fixedInputs": {"filename_prefix": {"type": "text", "label": "Filename prefix"}}, "outputs": {"type": "image"}},
    "SaveImageNode": {"fixedInputs": {"filename_prefix": {"type": "text", "label": "Filename prefix"}}, "outputs": {"type": "image"}},
    "VHS_VideoCombine": {"fixedInputs": {}, "outputs": {"type": "video"}},
    "VAEDecode": {
        "fixedInputs": {},
    },
    "PrimitiveStringMultiline": {
        "fixedInputs": {
            "value": {"type": "text", "label": "Prompt"},
        }
    },
    "Power Lora Loader (rgthree)": {
        "repeatGroups": [
            {
                "match": LORA_GROUP_MATCH,
                "label": "LoRAs",
                "fields": {
                    "on": {"type": "boolean", "label": "Enabled", "hideLabel": True},
                    "lora": {"type": "select", "label": "LoRA", "hideLabel": True},
                    "strength": {
                        "type": "number",
                        "label": "Strength",
                        "min": 0,
                        "max": 2,
                        "step": 0.05,
                        "slider": True,
                    },
                },
            }
        ]
    },
    "EmptyLatentImage": {
        "fixedInputs": {
            "width": {"type": "number", "label": "Width", "min": 64, "max": 2048, "step": 8},
            "height": {"type": "number", "label": "Height", "min": 64, "max": 2048, "step": 8},
            "batch_size": {"type": "number", "label": "Batch size", "min": 1, "max": 64},
        },
    },
    "EmptySD3LatentImage": {
        "fixedInputs": {
            "width": {"type": "number", "label": "Width", "min": 64, "max": 2048, "step": 8},
            "height": {"type": "number", "label": "Height", "min": 64, "max": 2048, "step": 8},
            "batch_size": {"type": "number", "label": "Batch size", "min": 1, "max": 64},
        },
    },
    "SDXLEmptyLatentSizePicker+": {
        "fixedInputs": {
            "width_override": {"type": "number", "label": "Width", "min": 64, "max": 2048, "step": 8},
            "height_override": {"type": "number", "label": "Height", "min": 64, "max": 2048, "step": 8},
            "batch_size": {"type": "number", "label": "Batch size", "min": 1, "max": 64},
        },
    },
    "Int": {
        "fixedInputs": {
            "Number": {"type": "number", "label": "Value"},
        },
    },
    "Float": {
        "fixedInputs": {
            "Number": {"type": "number", "label": "Value"},
        },
    },
    "easy int": {
        "fixedInputs": {
            "value": {"type": "number", "label": "Value"},
        },
    },
    "easy seed": {
        "fixedInputs": {
            "seed": {"type": "seed", "label": "Seed"},
        },
    },
    "KSamplerAdvanced": {
        "fixedInputs": {
            "noise_seed": {"type": "seed", "label": "Seed"},
            "steps": {"type": "number", "label": "Steps", "min": 1, "max": 150, "slider": True},
            "cfg": {"type": "number", "label": "CFG Scale", "min": 1, "max": 20, "slider": True},
            "sampler_name": {"type": "select", "label": "Sampler", "optionSource": "samplers"},
            "scheduler": {"type": "select", "label": "Scheduler", "optionSource": "schedulers"},
        },
    },
    "LoraLoaderModelOnly": {
        "fixedInputs": {
            "lora_name": {"type": "select", "label": "LoRA", "optionSource": "loras"},
            "strength_model": {"type": "number", "label": "Strength", "min": 0, "max": 2, "step": 0.05, "slider": True},
        },
    },
    "LoraLoader": {
        "fixedInputs": {
            "lora_name": {"type": "select", "label": "LoRA", "optionSource": "loras"},
            "strength_model": {"type": "number", "label": "Strength (model)", "min": -100, "max": 100, "step": 0.01, "slider": True},
            "strength_clip": {"type": "number", "label": "Strength (CLIP)", "min": -100, "max": 100, "step": 0.01, "slider": True},
        },
    },
    "LycorisLoaderNode": {
        "fixedInputs": {
            "lora_name": {"type": "select", "label": "LoRA", "optionSource": "loras"},
            "strength_model": {"type": "number", "label": "Strength (model)", "min": -100, "max": 100, "step": 0.01, "slider": True},
            "strength_clip": {"type": "number", "label": "Strength (CLIP)", "min": -100, "max": 100, "step": 0.01, "slider": True},
            "lycoris_type": {"type": "select", "label": "LyCORIS type", "optionSource": "lycoris_types"},
        },
    },
    "KSamplerSelect": {
        "fixedInputs": {
            "sampler_name": {"type": "select", "label": "Sampler", "optionSource": "samplers"},
        },
    },
    "RandomNoise": {
        "fixedInputs": {
            "noise_seed": {"type": "seed", "label": "Seed"},
        },
    },
    "UNETLoader": {
        "fixedInputs": {
            "unet_name": {"type": "select", "label": "UNet model", "optionSource": "checkpoints"},
            "weight_dtype": {"type": "select", "label": "Weight dtype", "options": ["default", "fp8", "fp16", "bf16"]},
        },
    },
    "CLIPLoader": {
        "optionSourceForSelect": "clip_models",
        "fixedInputs": {
            "clip_name": {"type": "select", "label": "CLIP model", "optionSource": "clip_models"},
            "type": {"type": "select", "label": "Type", "optionSource": "clip_types"},
            "device": {"type": "select", "label": "Device", "optionSource": "devices"},
        },
    },
    "DualCLIPLoader": {
        "fixedInputs": {
            "clip_name1": {"type": "select", "label": "CLIP model 1", "optionSource": "clip_models"},
            "clip_name2": {"type": "select", "label": "CLIP model 2", "optionSource": "clip_models"},
            "type": {"type": "select", "label": "Type", "optionSource": "clip_types"},
            "device": {"type": "select", "label": "Device", "optionSource": "devices"},
        },
    },
    "TripleCLIPLoader": {
        "fixedInputs": {
            "clip_name1": {"type": "select", "label": "CLIP model 1", "optionSource": "clip_models"},
            "clip_name2": {"type": "select", "label": "CLIP model 2", "optionSource": "clip_models"},
            "clip_name3": {"type": "select", "label": "CLIP model 3", "optionSource": "clip_models"},
            "type": {"type": "select", "label": "Type", "optionSource": "clip_types"},
            "device": {"type": "select", "label": "Device", "optionSource": "devices"},
        },
    },
    "CLIPVisionLoader": {
        "fixedInputs": {
            "clip_name": {"type": "select", "label": "CLIP Vision model", "optionSource": "clip_vision_models"},
        },
    },
    "T5Loader": {
        "fixedInputs": {
            "t5_name": {"type": "select", "label": "T5 model", "optionSource": "clip_models"},
        },
    },
    "TextEncoderLoader": {
        "fixedInputs": {
            "name": {"type": "select", "label": "Text encoder model", "optionSource": "clip_models"},
        },
    },
    "VAELoader": {
        "fixedInputs": {
            "vae_name": {"type": "select", "label": "VAE", "optionSource": "vae_models"},
        },
    },
    "EmptyFlux2LatentImage": {
        "fixedInputs": {
            "width": {"type": "number", "label": "Width", "min": 64, "max": 2048, "step": 8},
            "height": {"type": "number", "label": "Height", "min": 64, "max": 2048, "step": 8},
            "batch_size": {"type": "number", "label": "Batch size", "min": 1, "max": 64},
        },
    },
    "ImageScaleToTotalPixels": {
        "fixedInputs": {
            "upscale_method": {"type": "select", "label": "Upscale method", "options": ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]},
            "megapixels": {"type": "number", "label": "Megapixels", "min": 0.1, "max": 100, "step": 0.1},
            "resolution_steps": {"type": "number", "label": "Resolution steps", "min": 1, "max": 16},
            "image": {"type": "image", "label": "Image"},
        },
    },
    "Flux2Scheduler": {
        "fixedInputs": {
            "steps": {"type": "number", "label": "Steps", "min": 1, "max": 150, "slider": True},
        },
    },
    "BasicScheduler": {
        "fixedInputs": {
            "scheduler": {"type": "select", "label": "Scheduler", "optionSource": "schedulers"},
            "steps": {"type": "number", "label": "Steps", "min": 1, "max": 150, "slider": True},
            "denoise": {"type": "number", "label": "Denoise", "min": 0, "max": 1, "step": 0.01, "slider": True},
        },
    },
    "SamplerCustomAdvanced": {"fixedInputs": {}},
    "CFGGuider": {"fixedInputs": {}},
    "ConditioningZeroOut": {"fixedInputs": {}},
    "GetImageSize": {"fixedInputs": {}},
    "ReferenceLatent": {"fixedInputs": {}},
    "VAEEncode": {"fixedInputs": {}},
    "ImageUpscaleWithModel": {"fixedInputs": {}},
    "Any Switch (rgthree)": {"fixedInputs": {}},
    "T5TokenizerOptions": {"fixedInputs": {}},
    "ModelSamplingAuraFlow": {
        "fixedInputs": {
            "shift": {"type": "number", "label": "Shift", "min": 0, "max": 10, "step": 0.1, "slider": True},
        },
    },
    "ImageScale": {
        "fixedInputs": {
            "upscale_method": {"type": "select", "label": "Upscale method", "options": ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]},
            "width": {"type": "number", "label": "Width", "min": 64, "max": 8192, "step": 8},
            "height": {"type": "number", "label": "Height", "min": 64, "max": 8192, "step": 8},
            "crop": {"type": "select", "label": "Crop", "options": ["disabled", "center", "top", "bottom", "left", "right"]},
        },
    },
    "VAEEncodeTiled": {
        "fixedInputs": {
            "tile_size": {"type": "number", "label": "Tile size", "min": 64, "max": 2048, "step": 8},
            "overlap": {"type": "number", "label": "Overlap", "min": 0, "max": 512},
            "temporal_size": {"type": "number", "label": "Temporal size", "min": 1, "max": 256},
            "temporal_overlap": {"type": "number", "label": "Temporal overlap", "min": 0, "max": 128},
        },
    },
    "UpscaleModelLoader": {
        "fixedInputs": {
            "model_name": {"type": "select", "label": "Upscale model", "optionSource": "upscale_models"},
        },
    },
    "ESRGANLoader": {
        "fixedInputs": {
            "model_name": {"type": "select", "label": "Upscale model", "optionSource": "upscale_models"},
        },
    },
    "RealESRGANLoader": {
        "fixedInputs": {
            "model_name": {"type": "select", "label": "Upscale model", "optionSource": "upscale_models"},
        },
    },
    "SwinIRLoader": {
        "fixedInputs": {
            "model_name": {"type": "select", "label": "Upscale model", "optionSource": "upscale_models"},
        },
    },
    "VAEDecodeTiled": {
        "fixedInputs": {
            "tile_size": {"type": "number", "label": "Tile size", "min": 64, "max": 2048, "step": 8},
            "overlap": {"type": "number", "label": "Overlap", "min": 0, "max": 512},
            "temporal_size": {"type": "number", "label": "Temporal size", "min": 1, "max": 256},
            "temporal_overlap": {"type": "number", "label": "Temporal overlap", "min": 0, "max": 128},
        },
    },
    "LatentUpscaleBy": {
        "fixedInputs": {
            "upscale_method": {"type": "select", "label": "Upscale method", "options": ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]},
            "scale_by": {"type": "number", "label": "Scale by", "min": 0.25, "max": 4, "step": 0.25, "slider": True},
        },
    },
    "Seed (rgthree)": {
        "fixedInputs": {
            "seed": {"type": "seed", "label": "Seed"},
        },
    },
    "CR Latent Input Switch": {
        "fixedInputs": {
            "Input": {"type": "number", "label": "Input", "min": 1, "max": 2, "step": 1},
        },
    },
    "TextEncodeAceStepAudio1.5": {
        "fixedInputs": {
            "tags": {"type": "text", "label": "Tags / Description"},
            "lyrics": {"type": "text", "label": "Lyrics"},
            "seed": {"type": "seed", "label": "Seed"},
            "bpm": {"type": "number", "label": "BPM", "min": 1, "max": 300},
            "duration": {"type": "number", "label": "Duration (seconds)", "min": 1, "max": 600},
            "timesignature": {"type": "select", "label": "Time signature", "options": ["4", "3", "2", "6", "8"]},
            "language": {"type": "select", "label": "Language", "options": ["en", "zh", "ja", "de", "fr", "es", "it", "ko", "pt", "ru"]},
            "keyscale": {"type": "text", "label": "Key / Scale"},
            "cfg_scale": {"type": "number", "label": "CFG scale", "min": 1, "max": 10},
            "temperature": {"type": "number", "label": "Temperature", "min": 0.1, "max": 2},
            "top_p": {"type": "number", "label": "Top P", "min": 0, "max": 1},
            "top_k": {"type": "number", "label": "Top K", "min": 0, "max": 100},
        },
    },
    "EmptyAceStep1.5LatentAudio": {
        "fixedInputs": {
            "seconds": {"type": "number", "label": "Duration (seconds)", "min": 1, "max": 600},
            "batch_size": {"type": "number", "label": "Batch size", "min": 1, "max": 64},
        },
    },
    "SaveAudioMP3": {
        "fixedInputs": {
            "filename_prefix": {"type": "text", "label": "Filename prefix"},
            "quality": {"type": "select", "label": "Quality", "options": ["V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9"]},
        },
        "outputs": {"type": "audio"},
    },
    "AudioQualityEnhancer": {
        "fixedInputs": {
            "enhancement_level": {"type": "number", "label": "Enhancement level", "min": 0, "max": 3},
            "use_source_separation": {"type": "select", "label": "Use source separation", "options": ["true", "false"]},
            "demucs_model": {"type": "text", "label": "Demucs model"},
            "device": {"type": "select", "label": "Device", "optionSource": "devices"},
            "vocals_enhance": {"type": "number", "label": "Vocals", "min": 0, "max": 1},
            "drums_enhance": {"type": "number", "label": "Drums", "min": 0, "max": 1},
            "bass_enhance": {"type": "number", "label": "Bass", "min": 0, "max": 1},
            "other_enhance": {"type": "number", "label": "Other", "min": 0, "max": 1},
            "clarity": {"type": "number", "label": "Clarity", "min": 0, "max": 1},
            "dynamics": {"type": "number", "label": "Dynamics", "min": 0, "max": 1},
            "warmth": {"type": "number", "label": "Warmth", "min": 0, "max": 1},
            "air": {"type": "number", "label": "Air", "min": 0, "max": 1},
            "dolby_effect": {"type": "number", "label": "Dolby effect", "min": 0, "max": 2},
            "simple_mode": {"type": "select", "label": "Simple mode", "options": ["Standard", "Simple", "Minimal"]},
            "apply_limiter": {"type": "select", "label": "Apply limiter", "options": ["true", "false"]},
        },
    },
    "ModelSamplingSD3": {
        "fixedInputs": {
            "shift": {"type": "number", "label": "Shift", "min": 0, "max": 10, "step": 0.1, "slider": True},
        },
    },
    "INTConstant": {
        "fixedInputs": {
            "value": {"type": "number", "label": "Value"},
        },
    },
    "UnetLoaderGGUF": {
        "fixedInputs": {
            "unet_name": {"type": "select", "label": "UNet model (GGUF)", "optionSource": "unet_gguf_models"},
        },
    },
    "RIFE VFI": {
        "fixedInputs": {
            "ckpt_name": {"type": "select", "label": "RIFE model", "optionSource": "rife_models"},
            "multiplier": {"type": "number", "label": "Multiplier", "min": 1, "max": 16, "step": 1},
            "clear_cache_after_n_frames": {"type": "number", "label": "Clear cache after N frames", "min": 1, "max": 64},
            "fast_mode": {"type": "boolean", "label": "Fast mode"},
            "ensemble": {"type": "boolean", "label": "Ensemble"},
            "scale_factor": {"type": "number", "label": "Scale factor", "min": 0.25, "max": 4, "step": 0.25},
        },
    },
    "ImageResizeKJv2": {
        "fixedInputs": {
            "width": {"type": "number", "label": "Width", "min": 64, "max": 8192, "step": 8},
            "height": {"type": "number", "label": "Height", "min": 64, "max": 8192, "step": 8},
            "upscale_method": {"type": "select", "label": "Upscale method", "options": ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]},
            "keep_proportion": {"type": "select", "label": "Keep proportion", "options": ["resize", "crop", "pad"]},
            "pad_color": {"type": "text", "label": "Pad color"},
            "crop_position": {"type": "select", "label": "Crop position", "options": ["center", "top", "bottom", "left", "right"]},
            "divisible_by": {"type": "number", "label": "Divisible by", "min": 1, "max": 64, "step": 1},
            "device": {"type": "select", "label": "Device", "optionSource": "devices"},
            "image": {"type": "image", "label": "Image"},
        },
    },
    "Text Multiline": {
        "fixedInputs": {
            "text": {"type": "text", "label": "Prompt"},
        },
    },
}


def _parse_workflow_ui_link_definitions(raw: Any) -> list[dict[str, Any]]:
    """Parse JSON from input_definitions or output_definitions. Returns [] on failure."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = __import__("json").loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            pass
    return []


WORKFLOW_UI_LINK_TYPES = (WORKFLOW_UI_LINK_CLASS, "WorkflowUI Link")


def workflow_contains_workflow_ui_link(workflow: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (has_link, first_link_node_id or None)."""
    wf = _normalize_to_api_format(workflow)
    for nid, n in wf.items():
        if isinstance(n, dict) and n.get("class_type") in WORKFLOW_UI_LINK_TYPES:
            return True, nid
    return False, None


def extract_form_label_from_graph(workflow: dict[str, Any]) -> str | None:
    """Extract form_label from the WorkflowUILink node in the graph, if present."""
    wf = _normalize_to_api_format(workflow)
    for nid, n in wf.items():
        if isinstance(n, dict) and n.get("class_type") in WORKFLOW_UI_LINK_TYPES:
            inputs = n.get("inputs") or {}
            fl = (inputs.get("form_label") or "").strip()
            return fl if fl else None
    return None


def _workflow_ui_link_field(slot: int, typ: str) -> str:
    """Map definition type to actual input field name for WorkflowUILink node."""
    if typ == "image":
        return f"input_image_{slot}"
    if typ == "video":
        return f"input_video_{slot}"
    if typ == "audio":
        return f"input_audio_{slot}"
    if typ == "boolean":
        return f"input_boolean_{slot}"
    if typ in ("number", "seed"):
        return f"input_number_{slot}"
    return f"input_text_{slot}"


def _find_input_definitions_fallback(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """When input_definitions is missing, scan values for a JSON array of {name, type} objects."""
    import json as _json
    for v in inputs.values():
        if not isinstance(v, str) or not v.strip().startswith("["):
            continue
        try:
            parsed = _json.loads(v)
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                if "name" in parsed[0] or "type" in parsed[0]:
                    return parsed
        except Exception:
            pass
    return []


def _parse_workflow_ui_link_output_name(name: str) -> tuple[int | None, str | None]:
    """Parse output name like text_0, number_1, image_2 -> (slot, type)."""
    for prefix in ("text_", "number_", "image_", "video_", "audio_"):
        if name.startswith(prefix):
            try:
                slot = int(name[len(prefix):])
                if 0 <= slot < 8:
                    typ = "number" if prefix == "number_" else prefix.rstrip("_")
                    return slot, typ
            except ValueError:
                pass
    return None, None


def _origin_slot_to_slot_and_type(origin_slot: int) -> tuple[int, str] | None:
    """Map WorkflowUILink output index (origin_slot) to (slot 0-7, type)."""
    if origin_slot < 0 or origin_slot >= 40:
        return None
    slot = origin_slot % 8
    if origin_slot < 8:
        return slot, "text"
    if origin_slot < 16:
        return slot, "number"
    if origin_slot < 24:
        return slot, "image"
    if origin_slot < 32:
        return slot, "video"
    return slot, "audio"


def _infer_input_definitions_from_links(
    link_node_id: str,
    links: list[Any],
    node_inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Infer input definitions from workflow links array (ComfyUI 0.4 format).
    Links format: [link_id, origin_id, origin_slot, target_id, target_slot, type] (6 elements)."""
    if not isinstance(links, list):
        return []
    link_node_id_str = str(link_node_id)
    by_slot: dict[int, tuple[str, str]] = {}
    for link in links:
        if isinstance(link, (list, tuple)) and len(link) >= 4:
            if len(link) >= 6:
                origin_id, origin_slot = str(link[1]), link[2]
            else:
                origin_id, origin_slot = str(link[0]), link[1]
            if str(origin_id) != link_node_id_str or origin_slot is None:
                continue
            try:
                origin_slot_int = int(origin_slot)
            except (TypeError, ValueError):
                continue
            mapped = _origin_slot_to_slot_and_type(origin_slot_int)
            if mapped is None:
                continue
            slot, typ = mapped
            name_val = (node_inputs.get(f"name_{slot}") or node_inputs.get(f"title_{slot}") or "").strip()
            label = name_val or f"Field {slot}"
            use_seed = typ == "number" and "seed" in label.lower()
            dtype = "seed" if use_seed else typ
            name_slug = label.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "") or f"field_{slot}"
            if slot not in by_slot:
                by_slot[slot] = (dtype, label, name_slug)
        elif isinstance(link, dict):
            origin_id = str(link.get("origin_id", link.get("originId", "")))
            origin_slot = link.get("origin_slot", link.get("originSlot"))
            if origin_id != link_node_id_str or origin_slot is None:
                continue
            try:
                origin_slot_int = int(origin_slot)
            except (TypeError, ValueError):
                continue
            mapped = _origin_slot_to_slot_and_type(origin_slot_int)
            if mapped is None:
                continue
            slot, typ = mapped
            name_val = (node_inputs.get(f"name_{slot}") or node_inputs.get(f"title_{slot}") or "").strip()
            label = name_val or f"Field {slot}"
            use_seed = typ == "number" and "seed" in label.lower()
            dtype = "seed" if use_seed else typ
            name_slug = label.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "") or f"field_{slot}"
            if slot not in by_slot:
                by_slot[slot] = (dtype, label, name_slug)
    result: list[dict[str, Any]] = []
    for slot in sorted(by_slot.keys()):
        dtype, label, name_slug = by_slot[slot]
        result.append({"name": name_slug, "type": dtype, "label": label})
    return result


def _infer_input_definitions_from_names(node_inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback: build definitions from name_0..name_7 when outputs inference fails."""
    result: list[dict[str, Any]] = []
    for i in range(8):
        name = (node_inputs.get(f"name_{i}") or node_inputs.get(f"title_{i}") or "").strip()
        if not name:
            continue
        use_seed = "seed" in name.lower()
        name_slug = name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "") or f"field_{i}"
        typ = "seed" if use_seed else ("number" if any(x in name.lower() for x in ["width", "height", "steps", "px", "size"]) else "text")
        result.append({"name": name_slug, "type": typ})
    return result


def _infer_input_definitions_from_outputs(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Infer input definitions from WorkflowUILink outputs and title widgets when input_definitions is [].
    Used when workflow was saved with empty definitions but has outputs wired and titles set."""
    raw_outputs = node.get("_raw_outputs")
    if not isinstance(raw_outputs, list):
        return []
    node_inputs = node.get("inputs") or {}
    by_slot: dict[int, tuple[str, str, str, bool]] = {}
    for out in raw_outputs:
        if not isinstance(out, dict):
            continue
        name = out.get("name")
        if not name or not isinstance(name, str):
            continue
        links = out.get("links")
        has_link = isinstance(links, list) and len(links) > 0
        slot, typ = _parse_workflow_ui_link_output_name(name)
        if slot is None or typ is None:
            continue
        name_val = (node_inputs.get(f"name_{slot}") or node_inputs.get(f"title_{slot}") or "").strip()
        if not has_link and not name_val:
            continue
        label = name_val or f"Field {slot}"
        use_seed = typ == "number" and "seed" in label.lower()
        dtype = "seed" if use_seed else typ
        name_slug = label.lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "") or f"field_{slot}"
        prev = by_slot.get(slot)
        if prev is None or (has_link and not prev[3]):
            by_slot[slot] = (dtype, label, name_slug, has_link)
    result: list[dict[str, Any]] = []
    for slot in sorted(by_slot.keys()):
        dtype, label, name_slug, _ = by_slot[slot]
        result.append({"name": name_slug, "type": dtype, "label": label})
    return result


def _input_definitions_from_type_widgets(node_inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Build input_definitions from type_0..7, name_0..7 widgets. Name is used as both identifier and label."""
    result: list[dict[str, Any]] = []
    for i in range(8):
        typ = (node_inputs.get(f"type_{i}") or "").strip().lower()
        if not typ:
            continue
        name = (node_inputs.get(f"name_{i}") or "").strip()
        if not name:
            name = f"field_{i}"
        result.append({"name": name, "type": typ})
    return result


def _analyze_workflow_ui_link_node(
    node_id: str,
    node: dict[str, Any],
    workflow: dict[str, Any],
    *,
    raw_links: list[Any] | None = None,
) -> dict[str, Any]:
    """Build inputs from WorkflowUILink node; outputs from rest of graph (SaveImage etc.)."""
    node_inputs = node.get("inputs") or {}
    input_defs = _input_definitions_from_type_widgets(node_inputs)
    if not input_defs:
        input_defs = _parse_workflow_ui_link_definitions(node_inputs.get("input_definitions"))
    if not input_defs:
        input_defs = _find_input_definitions_fallback(node_inputs)
    if not input_defs:
        input_defs = _infer_input_definitions_from_outputs(node)
    if not input_defs and raw_links:
        input_defs = _infer_input_definitions_from_links(node_id, raw_links, node_inputs)
    if not input_defs:
        input_defs = _infer_input_definitions_from_names(node_inputs)
    meta = node.get("_meta") or {}
    node_title = (meta.get("title") or "WorkflowUILink").replace("_", " ")
    meta_title = (meta.get("title") or "").replace("_", " ") or None

    inputs: list[dict[str, Any]] = []
    bindings: list[dict[str, str]] = []

    for i, item in enumerate(input_defs):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name or not isinstance(name, str):
            continue
        typ = (item.get("type") or "text").lower()
        field = _workflow_ui_link_field(i, typ)
        key = f"{node_id}.{field}"
        label = (item.get("label") or name).replace("_", " ")
        is_seed = typ == "seed"
        inp = {
            "key": key,
            "label": label,
            "role": "seed" if is_seed else "parameter",
            "parent": node_title,
            "type": typ if typ in ("text", "number", "seed", "image", "video", "audio", "select", "boolean") else "text",
            "default": node_inputs.get(field) if field in node_inputs else item.get("default"),
            "nodeId": node_id,
            "field": field,
            "classType": WORKFLOW_UI_LINK_CLASS,
            "metaTitle": meta_title,
        }
        if name:
            inp["name"] = name
        for k in ("min", "max", "step", "slider", "options", "optionSource"):
            if k in item:
                inp[k] = item[k]
        inputs.append(inp)
        bindings.append({"key": key, "nodeId": node_id, "field": field})

    outputs: list[dict[str, Any]] = []
    for nid, n in workflow.items():
        if nid == node_id or not isinstance(n, dict):
            continue
        spec = NODE_SPECS.get(n.get("class_type") or "")
        if not spec:
            continue
        out_spec = spec.get("outputs") or {}
        if not out_spec:
            continue
        meta = n.get("_meta") or {}
        node_title = (meta.get("title") or n.get("class_type") or nid).replace("_", " ")
        out_meta_title = (meta.get("title") or "").replace("_", " ") if meta.get("title") else None
        if out_spec.get("type") == "image":
            outputs.append({"nodeId": nid, "type": "image", "label": node_title, "metaTitle": out_meta_title})
        if out_spec.get("type") == "video":
            outputs.append({"nodeId": nid, "type": "video", "label": node_title, "metaTitle": out_meta_title})
        if out_spec.get("type") == "audio":
            outputs.append({"nodeId": nid, "type": "audio", "label": node_title, "metaTitle": out_meta_title})

    form_label = (node_inputs.get("form_label") or "").strip()
    result: dict[str, Any] = {"inputs": inputs, "outputs": outputs, "bindings": bindings}
    if form_label:
        result["form_label"] = form_label
    return result


def analyze_workflow(workflow: dict[str, Any], use_workflow_ui_link: bool = False) -> dict[str, Any]:
    raw_workflow = _extract_workflow_for_analysis(workflow) if isinstance(workflow, dict) else {}
    raw_links = raw_workflow.get("links") if isinstance(raw_workflow, dict) else None
    workflow = _normalize_to_api_format(workflow)
    inputs: list[dict[str, Any]] = []
    bindings: list[dict[str, str]] = []
    outputs: list[dict[str, Any]] = []
    internal_nodes: dict[str, str] = {}
    image_input_index = 0

    if use_workflow_ui_link:
        link_node_id = None
        link_node = None
        for nid, n in workflow.items():
            if isinstance(n, dict) and n.get("class_type") in WORKFLOW_UI_LINK_TYPES:
                link_node_id = nid
                link_node = n
                break
        if link_node_id is not None and link_node is not None:
            result = _analyze_workflow_ui_link_node(
                link_node_id, link_node, workflow, raw_links=raw_links
            )
            return result

    form_label: str | None = None
    has_link, link_node_id = workflow_contains_workflow_ui_link(workflow)
    if has_link and link_node_id:
        link_node = workflow.get(link_node_id)
        if isinstance(link_node, dict):
            link_result = _analyze_workflow_ui_link_node(
                link_node_id, link_node, workflow, raw_links=raw_links
            )
            inputs.extend(link_result.get("inputs") or [])
            bindings.extend(link_result.get("bindings") or [])
            form_label = link_result.get("form_label") or None

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        node_inputs = node.get("inputs") or {}

        if class_type == "CLIPTextEncode":
            text_in = node_inputs.get("text")
            if isinstance(text_in, list):
                continue
        if class_type == "Text Multiline":
            text_in = node_inputs.get("text")
            if isinstance(text_in, list):
                continue

        spec = NODE_SPECS.get(class_type) if class_type else None

        if not spec:
            meta = node.get("_meta") or {}
            title = meta.get("title")
            if title == "Prompt" and node_inputs:
                text_field = "value" if isinstance(node_inputs.get("value"), str) else ("text" if isinstance(node_inputs.get("text"), str) else None)
                if text_field:
                    key = f"{node_id}.{text_field}"
                    label = (title or "Prompt").replace("_", " ")
                    meta_title = (meta.get("title") or "").replace("_", " ") or None
                    inputs.append({
                        "key": key,
                        "label": label,
                        "role": "parameter",
                        "parent": (meta.get("title") or class_type or node_id).replace("_", " "),
                        "type": "text",
                        "default": node_inputs.get(text_field),
                        "nodeId": node_id,
                        "field": text_field,
                        "classType": class_type or "Unknown",
                        "metaTitle": meta_title or None,
                    })
                    bindings.append({"key": key, "nodeId": node_id, "field": text_field})
            continue

        meta = node.get("_meta") or {}
        node_title = (meta.get("title") or "").replace("_", " ") if meta.get("title") else class_type
        if isinstance(node_title, str):
            node_title = node_title.replace("_", " ")

        fixed = spec.get("fixedInputs") or {}
        has_no_fixed = len(fixed) == 0
        has_no_outputs = not spec.get("outputs")
        has_no_repeat_groups = not spec.get("repeatGroups")

        if class_type in OUTPUT_ONLY_NODE_TYPES:
            out_spec = spec.get("outputs") or {}
            out_meta_title = (meta.get("title") or "").replace("_", " ") if meta.get("title") else None
            if out_spec.get("type") == "image":
                label = node_title or node_id
                outputs.append({"nodeId": node_id, "type": "image", "label": label, "metaTitle": out_meta_title})
            if out_spec.get("type") == "video":
                label = node_title or node_id
                outputs.append({"nodeId": node_id, "type": "video", "label": label, "metaTitle": out_meta_title})
            if out_spec.get("type") == "audio":
                label = node_title or node_id
                outputs.append({"nodeId": node_id, "type": "audio", "label": label, "metaTitle": out_meta_title})
            continue

        layout_rows = (spec.get("layout") or {}).get("rows") or []
        layout_map = _layout_map(layout_rows)

        for field, defn in fixed.items():
            if field not in node_inputs:
                continue
            key = f"{node_id}.{field}"
            is_seed = (defn.get("type") or "") == "seed"
            if field == "text":
                label = node_title
            elif defn.get("type") == "image":
                image_input_index += 1
                label = f"{defn.get('label') or 'Image'} {image_input_index}"
            else:
                label = defn.get("label") or f"{node_title} – {field}"

            layout = layout_map.get(field)
            meta_title = (meta.get("title") or "").replace("_", " ") if meta.get("title") else None
            inp = {
                "key": key,
                "label": label,
                "role": "seed" if is_seed else "parameter",
                "parent": node_title,
                "type": defn.get("type", "text"),
                "default": node_inputs.get(field),
                "nodeId": node_id,
                "field": field,
                "classType": class_type,
                "metaTitle": meta_title,
            }
            if defn.get("hideLabel") is True:
                inp["hideLabel"] = True
            for k in ("min", "max", "step", "slider", "options", "optionSource"):
                if k in defn:
                    inp[k] = defn[k]
            if layout is not None:
                inp["layoutRow"] = layout.get("row")
                inp["layoutCol"] = layout.get("col")
            inputs.append(inp)
            bindings.append({"key": key, "nodeId": node_id, "field": field})

        for group in spec.get("repeatGroups") or []:
            pattern = group.get("match")
            if not pattern:
                continue
            group_fields = group.get("fields") or {}
            group_layout = (group.get("layout") or {}).get("rows") or []
            grp_layout_map = _layout_map(group_layout)

            for input_key, input_value in node_inputs.items():
                if not isinstance(input_value, dict):
                    continue
                if not pattern.match(input_key):
                    continue
                for field_key, field_spec in group_fields.items():
                    if field_key not in input_value:
                        continue
                    key = f"{node_id}.{input_key}.{field_key}"
                    raw = input_value.get(field_key)
                    if field_key == "lora" and isinstance(raw, str):
                        default_val = raw.split("/")[-1].replace(".safetensors", "") if raw else raw
                    else:
                        default_val = raw
                    meta_title = (meta.get("title") or "").replace("_", " ") if meta.get("title") else None
                    inp = {
                        "key": key,
                        "label": field_spec.get("label", field_key),
                        "role": "parameter",
                        "parent": node_title,
                        "type": field_spec.get("type", "text"),
                        "default": default_val,
                        "nodeId": node_id,
                        "field": f"{input_key}.{field_key}",
                        "classType": class_type,
                        "groupKey": input_key,
                        "metaTitle": meta_title,
                    }
                    if field_spec.get("hideLabel"):
                        inp["hideLabel"] = True
                    for k in ("min", "max", "step", "slider", "options", "optionSource"):
                        if k in field_spec:
                            inp[k] = field_spec[k]
                    layout = grp_layout_map.get(field_key)
                    if layout is not None:
                        inp["layoutRow"] = layout.get("row")
                        inp["layoutCol"] = layout.get("col")
                    inputs.append(inp)
                    bindings.append({"key": key, "nodeId": node_id, "field": f"{input_key}.{field_key}"})

        out_spec = spec.get("outputs") or {}
        out_meta_title = (meta.get("title") or "").replace("_", " ") if meta.get("title") else None
        if out_spec.get("type") == "image":
            label = node_title or node_id
            outputs.append({"nodeId": node_id, "type": "image", "label": label, "metaTitle": out_meta_title})
        if out_spec.get("type") == "video":
            label = node_title or node_id
            outputs.append({"nodeId": node_id, "type": "video", "label": label, "metaTitle": out_meta_title})
        if out_spec.get("type") == "audio":
            label = node_title or node_id
            outputs.append({"nodeId": node_id, "type": "audio", "label": label, "metaTitle": out_meta_title})

        if has_no_fixed and has_no_outputs and has_no_repeat_groups:
            label = node_title or class_type or node_id
            internal_nodes[class_type] = label

    result: dict[str, Any] = {"inputs": inputs, "outputs": outputs, "bindings": bindings}
    if internal_nodes:
        result["internal_nodes"] = [{"classType": k, "label": v} for k, v in internal_nodes.items()]
    if form_label:
        result["form_label"] = form_label
    return result
