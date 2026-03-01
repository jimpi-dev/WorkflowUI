import re
from typing import Any

_WIDGET_ORDER: dict[str, list[str]] = {
    "EmptyLatentImage": ["width", "height", "batch_size"],
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "SDXLEmptyLatentSizePicker+": ["resolution", "batch_size", "width_override", "height_override"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "UNETLoader": ["unet_name", "weight_dtype"],
}


def _normalize_to_api_format(workflow: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(workflow, dict):
        return workflow
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
        inputs: dict[str, Any] = {}
        widget_order = _WIDGET_ORDER.get(class_type)
        widgets_values = node.get("widgets_values")
        if isinstance(widgets_values, list) and widget_order:
            for idx, field in enumerate(widget_order):
                if idx < len(widgets_values):
                    inputs[field] = widgets_values[idx]
        elif isinstance(node.get("inputs"), dict):
            inputs = dict(node["inputs"])
        meta = node.get("_meta")
        if not meta and isinstance(node.get("properties"), dict):
            s_r_name = (node.get("properties") or {}).get("Node name for S&R")
            if isinstance(s_r_name, str) and s_r_name.strip():
                meta = {"title": s_r_name.strip()}
        if meta:
            out[node_id] = {"class_type": class_type, "inputs": inputs, "_meta": meta}
        else:
            out[node_id] = {"class_type": class_type, "inputs": inputs}
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
}


def analyze_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    workflow = _normalize_to_api_format(workflow)
    inputs: list[dict[str, Any]] = []
    bindings: list[dict[str, str]] = []
    outputs: list[dict[str, Any]] = []
    internal_nodes: dict[str, str] = {}
    image_input_index = 0

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        node_inputs = node.get("inputs") or {}

        if class_type == "CLIPTextEncode":
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
    return result
