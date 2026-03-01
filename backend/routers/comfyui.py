import requests

from fastapi import APIRouter

from dependencies import COMFY_URL

router = APIRouter()


@router.get("/object_info")
def get_object_info():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("object_info fetch failed:", e)
        return {"samplers": [], "schedulers": []}
    samplers = []
    schedulers = []
    for node_name, node_info in obj.items():
        if not isinstance(node_info, dict):
            continue
        inputs = node_info.get("input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            if name == "sampler_name" and isinstance(options, list):
                for o in options:
                    if isinstance(o, str) and o not in samplers:
                        samplers.append(o)
            if name == "scheduler" and isinstance(options, list):
                for o in options:
                    if isinstance(o, str) and o not in schedulers:
                        schedulers.append(o)
    return {"samplers": samplers, "schedulers": schedulers}


@router.get("/checkpoints")
def get_checkpoints():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[checkpoints] object_info fetch failed:", e)
        return {"checkpoints": []}
    checkpoints = []
    seen = set()

    def add_checkpoint(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if not (s.lower().endswith(".safetensors") or s.lower().endswith(".ckpt")):
            return
        if s not in seen:
            seen.add(s)
            checkpoints.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_checkpoint(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_checkpoint(o[0])

    for node_name, node_info in obj.items():
        if not isinstance(node_info, dict):
            continue
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if name != "ckpt_name" or not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            extract_from_options(options)
            break
    result = sorted(checkpoints)
    return {"checkpoints": result}


@router.get("/clip_models")
def get_clip_models():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[clip_models] object_info fetch failed:", e)
        return {"clip_models": []}
    clip_models = []
    seen = set()

    def add_clip(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            clip_models.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_clip(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_clip(o[0])

    for node_name, node_info in obj.items():
        if not isinstance(node_info, dict):
            continue
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if name != "clip_name" or not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            extract_from_options(options)
            break
    result = sorted(clip_models)
    return {"clip_models": result}


@router.get("/clip_types")
def get_clip_types():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[clip_types] object_info fetch failed:", e)
        return {"clip_types": []}
    clip_types = []
    seen = set()

    def add_type(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            clip_types.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_type(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_type(o[0])

    node_info = obj.get("CLIPLoader")
    if isinstance(node_info, dict):
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if name != "type" or not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            extract_from_options(options)
            break
    result = sorted(clip_types)
    return {"clip_types": result}


@router.get("/devices")
def get_devices():
    devices = []
    seen = set()

    def add_device(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            devices.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_device(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_device(o[0])

    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[devices] object_info fetch failed:", e)
    else:
        node_info = obj.get("CLIPLoader")
        if isinstance(node_info, dict):
            inputs = node_info.get("input") or node_info.get("Input") or {}
            required = inputs.get("required") or {}
            optional = inputs.get("optional") or {}
            for name, spec in {**required, **optional}.items():
                if name != "device" or not isinstance(spec, list) or len(spec) < 1:
                    continue
                options = spec[0]
                extract_from_options(options)
                break

    if not devices:
        try:
            res = requests.get(f"{COMFY_URL}/system_stats", timeout=5)
            res.raise_for_status()
            data = res.json()
        except Exception as e:
            print("[devices] system_stats fetch failed:", e)
        else:
            raw_devices = data.get("devices") if isinstance(data.get("devices"), list) else []
            for d in raw_devices:
                if not isinstance(d, dict):
                    continue
                name = d.get("name") or d.get("device_name") or d.get("device")
                if isinstance(name, str) and name.strip():
                    add_device(name.strip())

    if not devices:
        for d in ["default", "cpu", "cuda"]:
            add_device(d)

    result = sorted(devices)
    return {"devices": result}


@router.get("/vae_models")
def get_vae_models():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[vae_models] object_info fetch failed:", e)
        return {"vae_models": []}
    vae_models = []
    seen = set()

    def add_vae(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            vae_models.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_vae(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_vae(o[0])

    for node_name, node_info in obj.items():
        if not isinstance(node_info, dict):
            continue
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if name != "vae_name" or not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            extract_from_options(options)
            break
    result = sorted(vae_models)
    return {"vae_models": result}


@router.get("/loras")
def get_loras():
    print("[loras] GET /loras called")
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[loras] object_info fetch failed:", e)
        return {"loras": []}
    loras = []
    seen = set()
    nodes_with_lora = []

    def add_lora(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if not s.lower().endswith(".safetensors"):
            return
        if s not in seen:
            seen.add(s)
            loras.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_lora(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_lora(o[0])

    for node_name, node_info in obj.items():
        if not isinstance(node_info, dict):
            continue
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            if name == "lora_name":
                nodes_with_lora.append((node_name, name))
                extract_from_options(options)
            elif "lora" in name.lower() and isinstance(options, list):
                nodes_with_lora.append((node_name, name))
                extract_from_options(options)
    result = sorted(loras)
    print("[loras] nodes with lora input:", nodes_with_lora[:15], "..." if len(nodes_with_lora) > 15 else "")
    print("[loras] returning", len(result), "loras", ("e.g. " + str(result[:5]) if result else "(none)"))
    return {"loras": result}


@router.get("/lycoris_types")
def get_lycoris_types():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[lycoris_types] object_info fetch failed:", e)
        return {"lycoris_types": []}
    node_info = obj.get("LycorisLoaderNode")
    if not isinstance(node_info, dict):
        return {"lycoris_types": []}
    inputs = node_info.get("input") or node_info.get("Input") or {}
    optional = inputs.get("optional") or {}
    spec = optional.get("lycoris_type")
    if not isinstance(spec, (list, tuple)) or len(spec) < 1:
        return {"lycoris_types": []}
    options = spec[0]
    if not isinstance(options, list):
        return {"lycoris_types": []}
    lycoris_types = [str(o) for o in options if isinstance(o, str)]
    return {"lycoris_types": lycoris_types}


@router.get("/rife_models")
def get_rife_models():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[rife_models] object_info fetch failed:", e)
        return {"rife_models": []}
    rife_models = []
    seen = set()

    def add_model(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            rife_models.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_model(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_model(o[0])

    node_info = obj.get("RIFE VFI")
    if isinstance(node_info, dict):
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if name != "ckpt_name" or not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            extract_from_options(options)
            break
    result = sorted(rife_models)
    return {"rife_models": result}


@router.get("/unet_gguf_models")
def get_unet_gguf_models():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[unet_gguf_models] object_info fetch failed:", e)
        return {"unet_gguf_models": []}
    unet_gguf_models = []
    seen = set()

    def add_model(s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            unet_gguf_models.append(s)

    def extract_from_options(options) -> None:
        if not isinstance(options, list):
            return
        for o in options:
            if isinstance(o, str):
                add_model(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                add_model(o[0])

    node_info = obj.get("UnetLoaderGGUF")
    if isinstance(node_info, dict):
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        for name, spec in {**required, **optional}.items():
            if name != "unet_name" or not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            extract_from_options(options)
            break
    result = sorted(unet_gguf_models)
    return {"unet_gguf_models": result}


@router.get("/stable_cascade_models")
def get_stable_cascade_models():
    try:
        res = requests.get(f"{COMFY_URL}/object_info", timeout=10)
        res.raise_for_status()
        obj = res.json()
    except Exception as e:
        print("[stable_cascade_models] object_info fetch failed:", e)
        return {"stage_b": [], "stage_c": []}
    stage_b = []
    stage_c = []
    seen_b = set()
    seen_c = set()

    def add_model(items: list, seen: set, s: str) -> None:
        if not isinstance(s, str) or not s.strip():
            return
        s = s.strip()
        if s not in seen:
            seen.add(s)
            items.append(s)

    def extract_list(options) -> list:
        out = []
        if not isinstance(options, list):
            return out
        for o in options:
            if isinstance(o, str):
                out.append(o)
            elif isinstance(o, (list, tuple)) and len(o) > 0 and isinstance(o[0], str):
                out.append(o[0])
        return out

    for node_name, node_info in obj.items():
        if not isinstance(node_info, dict):
            continue
        inputs = node_info.get("input") or node_info.get("Input") or {}
        required = inputs.get("required") or {}
        optional = inputs.get("optional") or {}
        all_inputs = {**required, **optional}
        if "key_opt_b" not in all_inputs or "key_opt_c" not in all_inputs:
            continue
        for key, dest, seen in (
            ("key_opt_b", stage_b, seen_b),
            ("key_opt_c", stage_c, seen_c),
        ):
            spec = all_inputs.get(key)
            if not isinstance(spec, list) or len(spec) < 1:
                continue
            options = spec[0]
            for o in extract_list(options):
                add_model(dest, seen, o)
        break
    return {"stage_b": sorted(stage_b), "stage_c": sorted(stage_c)}
